# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    x_mi_status = fields.Selection(
        [
            ("ok", "OK"),
            ("review", "Review"),
            ("blocked", "Blocked"),
        ],
        string="MI Status",
        default="ok",
        copy=False,
    )
    x_mi_check_ids = fields.One2many(
        "southbrook.mi.check", "production_id", string="Manufacturing Intelligence Checks"
    )
    x_mi_blocker_count = fields.Integer(string="MI Blockers", copy=False)
    x_mi_warning_count = fields.Integer(string="MI Warnings", copy=False)
    x_mi_next_action = fields.Text(string="MI Next Action", copy=False)
    x_mi_yield_pct = fields.Float(string="MI Sheet Yield %", copy=False)
    x_mi_waste_area_m2 = fields.Float(string="MI Waste Area m2", copy=False)
    x_mi_bottleneck_workcenter_id = fields.Many2one(
        "mrp.workcenter", string="MI Bottleneck Workcenter", copy=False
    )

    # ------------------------------------------------------------------
    # W012 — deviation-waiver warranty trace
    # ------------------------------------------------------------------
    # NOT a One2many because the canonical link lives on the waiver via
    # `production_id = related(mi_check_id.production_id, store=True)`.
    # Computing a count + an act_window button is enough surface; the
    # full waiver list is reachable through the smart button click.
    deviation_waiver_count = fields.Integer(
        string="Deviation Waivers",
        compute="_compute_deviation_waiver_count",
        help="Count of southbrook.deviation.waiver records bound to "
             "this MO via their mi_check_id.production_id linkage. The "
             "load-bearing field for warranty trace 18 months out — "
             '"did we ship this cabinet with a known defect?"',
    )

    @api.depends("x_mi_check_ids", "x_mi_check_ids.deviation_waiver_id")
    def _compute_deviation_waiver_count(self):
        Waiver = self.env["southbrook.deviation.waiver"]
        for prod in self:
            prod.deviation_waiver_count = Waiver.search_count(
                [("production_id", "=", prod.id)]
            )

    def action_open_deviation_waivers(self):
        """Smart button — show every waiver bound to this MO.

        Filters live on `production_id` which is a stored related on
        the waiver itself, so the search is index-supported.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Deviation Waivers"),
            "res_model": "southbrook.deviation.waiver",
            "view_mode": "list,form",
            "domain": [("production_id", "=", self.id)],
            "context": {"default_production_id": self.id},
        }

    def action_recompute_manufacturing_intelligence(self):
        engine = self.env["southbrook.mi.engine"]
        for production in self:
            engine._recompute_production(production)
        return True
