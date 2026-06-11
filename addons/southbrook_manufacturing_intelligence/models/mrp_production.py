# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


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

    def action_recompute_manufacturing_intelligence(self):
        engine = self.env["southbrook.mi.engine"]
        for production in self:
            engine._recompute_production(production)
        return True
