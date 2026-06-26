# SPDX-License-Identifier: LGPL-3.0-only
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookCmmsMtbfMttrReport(models.Model):
    _name = "southbrook.cmms.mtbf_mttr_report"
    _description = "CMMS MTBF / MTTR Report"
    _inherit = ["mail.thread"]
    _order = "as_of_date desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        default=lambda self: self._default_name(),
        tracking=True,
    )
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Equipment",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    as_of_date = fields.Date(
        string="As Of",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    period_days = fields.Integer(
        string="Period (days)",
        default=90,
        tracking=True,
    )
    breakdown_count = fields.Integer(
        string="Breakdowns",
        compute="_compute_metrics",
        store=True,
    )
    total_downtime_hours = fields.Float(
        string="Downtime (h)",
        compute="_compute_metrics",
        store=True,
    )
    total_runtime_hours = fields.Float(
        string="Runtime (h)",
        compute="_compute_metrics",
        store=True,
    )
    mtbf_hours = fields.Float(
        string="MTBF (h)",
        compute="_compute_metrics",
        store=True,
        help="Mean time between failures = runtime / max(1, breakdowns).",
    )
    mttr_hours = fields.Float(
        string="MTTR (h)",
        compute="_compute_metrics",
        store=True,
        help="Mean time to repair = downtime / max(1, breakdowns).",
    )
    availability_pct = fields.Float(
        string="Availability (%)",
        compute="_compute_metrics",
        store=True,
    )

    @api.model
    def _default_name(self):
        seq = self.env["ir.sequence"].next_by_code("southbrook.cmms.mtbf") or "0001"
        today = fields.Date.context_today(self)
        return "MTBF/%s/%s" % (today, seq)

    @api.depends("equipment_id", "as_of_date", "period_days")
    def _compute_metrics(self):
        Request = self.env["maintenance.request"]
        for rec in self:
            if not rec.equipment_id or not rec.as_of_date or not rec.period_days:
                rec.breakdown_count = 0
                rec.total_downtime_hours = 0.0
                rec.total_runtime_hours = 0.0
                rec.mtbf_hours = 0.0
                rec.mttr_hours = 0.0
                rec.availability_pct = 0.0
                continue
            period_start = rec.as_of_date - timedelta(days=rec.period_days)
            period_hours = float(rec.period_days) * 24.0
            domain = [
                ("equipment_id", "=", rec.equipment_id.id),
                ("maintenance_type", "=", "corrective"),
                ("request_date", ">=", period_start),
                ("request_date", "<=", rec.as_of_date),
            ]
            requests = Request.search(domain)
            downtime_h = 0.0
            for req in requests:
                start = req.request_date
                end = req.close_date or fields.Date.context_today(rec)
                if start and end:
                    delta_days = (end - start).total_seconds() / 86400.0 if hasattr(end, "total_seconds") else (end - start).days
                    # request_date / close_date are Date in v19; convert to hours via days * 24.
                    downtime_h += max(0.0, delta_days) * 24.0
            rec.breakdown_count = len(requests)
            rec.total_downtime_hours = downtime_h
            rec.total_runtime_hours = max(0.0, period_hours - downtime_h)
            denom = max(1, rec.breakdown_count)
            rec.mtbf_hours = rec.total_runtime_hours / denom
            rec.mttr_hours = rec.total_downtime_hours / denom
            rec.availability_pct = (
                (rec.total_runtime_hours / period_hours) * 100.0
                if period_hours else 0.0
            )

    def action_compute(self):
        self.invalidate_recordset([
            "breakdown_count", "total_downtime_hours", "total_runtime_hours",
            "mtbf_hours", "mttr_hours", "availability_pct",
        ])
        self._compute_metrics()
        return True

    @api.model
    def _cron_generate_daily_reports(self):
        Equipment = self.env["maintenance.equipment"].sudo()
        today = fields.Date.context_today(self)
        created = self.env[self._name]
        for eq in Equipment.search([("active", "=", True)]):
            rec = self.sudo().create({
                "equipment_id": eq.id,
                "as_of_date": today,
                "period_days": 90,
            })
            created |= rec
        _logger.info("CMMS daily MTBF/MTTR sweep: %d reports", len(created))
        return len(created)
