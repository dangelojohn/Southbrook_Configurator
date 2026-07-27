# SPDX-License-Identifier: LGPL-3.0-only
"""Bottleneck Report — live ranking of workcenter load."""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookMesMpsBottleneckReport(models.Model):
    _name = "southbrook.mes_mps.bottleneck_report"
    _description = "Bottleneck Report"
    _inherit = ["mail.thread"]
    _order = "as_of_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    as_of_date = fields.Date(
        string="As Of",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    line_ids = fields.One2many(
        "southbrook.mes_mps.bottleneck_line",
        "report_id",
        string="Lines",
    )
    top_bottleneck_workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Top Bottleneck",
        compute="_compute_top",
        store=True,
    )
    top_bottleneck_load_pct = fields.Float(
        string="Top Load %",
        compute="_compute_top",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "southbrook.mes_mps.bottleneck_report"
                )
                vals["name"] = seq or (
                    "BTLNCK/%s" % (vals.get("as_of_date") or "NEW")
                )
        return super().create(vals_list)

    @api.depends("line_ids", "line_ids.load_pct")
    def _compute_top(self):
        for rec in self:
            if rec.line_ids:
                top = max(rec.line_ids, key=lambda l: l.load_pct or 0.0)
                rec.top_bottleneck_workcenter_id = top.workcenter_id
                rec.top_bottleneck_load_pct = top.load_pct
            else:
                rec.top_bottleneck_workcenter_id = False
                rec.top_bottleneck_load_pct = 0.0

    def action_compute(self):
        """Refresh per-workcenter load for ``self.as_of_date``.

        Pulls workcenter capacity rows for the ISO week containing
        ``as_of_date``; if none exist, computes inline from
        mrp.workorder durations.
        """
        Capacity = self.env["southbrook.mes_mps.workcenter_capacity"]
        WO = self.env["mrp.workorder"]
        Workcenter = self.env["mrp.workcenter"]
        BLine = self.env["southbrook.mes_mps.bottleneck_line"]

        for rec in self:
            as_of = rec.as_of_date or fields.Date.context_today(rec)
            week_start = as_of - timedelta(days=as_of.weekday())
            week_end = week_start + timedelta(days=7)
            # Wipe previous lines so a recompute is idempotent.
            rec.line_ids.unlink()
            wcs = Workcenter.search([("active", "=", True)])
            line_vals = []
            for wc in wcs:
                cap = Capacity.search(
                    [
                        ("workcenter_id", "=", wc.id),
                        ("week_start", "=", week_start),
                    ],
                    limit=1,
                )
                if cap:
                    load = cap.load_pct
                    planned_h = cap.planned_hours
                else:
                    wos = WO.search(
                        [
                            ("workcenter_id", "=", wc.id),
                            ("date_start", ">=", week_start),
                            ("date_start", "<", week_end),
                            # Match the capacity model's filter — without it
                            # the fallback summed done/cancelled workorders too,
                            # inflating load and disagreeing with the capacity
                            # path for the same workcenter.
                            ("state", "in", ("blocked", "ready", "progress")),
                        ]
                    )
                    planned_h = (
                        sum(wos.mapped("duration_expected") or []) / 60.0
                    )
                    avail = 40.0
                    load = (
                        (planned_h / avail) * 100.0 if avail else 0.0
                    )
                # Downstream dependency count = how many distinct
                # routings reference this WC (proxy for criticality).
                bom_lines = self.env["mrp.routing.workcenter"].search_count(
                    [("workcenter_id", "=", wc.id)]
                )
                score = load * max(bom_lines, 1)
                if load >= 110:
                    action = "add_shift"
                elif load >= 90:
                    action = "outsource"
                elif load >= 75:
                    action = "split_order"
                else:
                    action = "no_action"
                line_vals.append({
                    "report_id": rec.id,
                    "workcenter_id": wc.id,
                    "load_pct": load,
                    "bottleneck_score": score,
                    "recommended_action": action,
                })
            if line_vals:
                BLine.create(line_vals)
        return True

    @api.model
    def cron_create_daily_report(self):
        """Cron entrypoint — fresh report + supervisor notification."""
        report = self.create({"as_of_date": fields.Date.context_today(self)})
        report.action_compute()
        # Notify the supervisor group via mail.thread.
        sup_group = self.env.ref(
            "southbrook_mes_mps.group_mes_manager",
            raise_if_not_found=False,
        )
        if sup_group and report.top_bottleneck_workcenter_id:
            # v19 renamed res.groups.users -> user_ids (the old name
            # AttributeError'd here, crashing the daily cron every run).
            partner_ids = sup_group.user_ids.mapped(
                "partner_id"
            ).ids
            if partner_ids:
                report.message_post(
                    body=_(
                        "Daily bottleneck report: %s loaded at %.1f%%."
                    ) % (
                        report.top_bottleneck_workcenter_id.display_name,
                        report.top_bottleneck_load_pct or 0.0,
                    ),
                    partner_ids=partner_ids,
                )
        return report
