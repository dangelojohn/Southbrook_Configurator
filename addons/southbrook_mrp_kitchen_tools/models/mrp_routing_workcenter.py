# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.routing.workcenter extension — operation tool requirements."""
from odoo import _, fields, models


class MrpRoutingWorkcenter(models.Model):
    _inherit = "mrp.routing.workcenter"

    southbrook_tool_requirement_ids = fields.One2many(
        "southbrook.operation.tool.requirement",
        "operation_id",
        string="Tool Requirements",
    )
    southbrook_tool_requirement_count = fields.Integer(
        compute="_compute_southbrook_tool_requirement_count",
    )

    def _compute_southbrook_tool_requirement_count(self):
        for rec in self:
            rec.southbrook_tool_requirement_count = len(
                rec.southbrook_tool_requirement_ids
            )
