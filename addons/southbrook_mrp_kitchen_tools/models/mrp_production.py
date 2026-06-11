# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.production extension — tool consumption cost rollup.

Aggregates southbrook.workorder.tool.consumption rows across all the
work orders of an MO into a single cost figure. Surfaces in the MO
form so production managers see tool cost alongside material cost
without having to drill into each WO.
"""
from odoo import _, api, fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    southbrook_tool_consumption_ids = fields.One2many(
        "southbrook.workorder.tool.consumption",
        "production_id",
        string="Tool Consumption Log",
    )
    southbrook_tool_consumption_count = fields.Integer(
        compute="_compute_southbrook_tool_consumption_count",
        string="# Tool Consumption Entries",
    )
    southbrook_tool_consumption_cost = fields.Float(
        compute="_compute_southbrook_tool_consumption_cost",
        string="Tool Consumption Cost",
        store=True,
        help="Rolled-up total_cost across all workorder.tool.consumption "
             "rows linked to this MO. Read against by the cost report "
             "alongside material and operation cost.",
    )

    @api.depends("southbrook_tool_consumption_ids.total_cost")
    def _compute_southbrook_tool_consumption_cost(self):
        for rec in self:
            rec.southbrook_tool_consumption_cost = sum(
                rec.southbrook_tool_consumption_ids.mapped("total_cost")
            )

    def _compute_southbrook_tool_consumption_count(self):
        for rec in self:
            rec.southbrook_tool_consumption_count = len(
                rec.southbrook_tool_consumption_ids
            )

    def action_view_southbrook_tool_consumption(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tool Consumption on %s") % self.name,
            "res_model": "southbrook.workorder.tool.consumption",
            "view_mode": "list,form",
            "domain": [("production_id", "=", self.id)],
            "context": {"default_production_id": self.id},
        }
