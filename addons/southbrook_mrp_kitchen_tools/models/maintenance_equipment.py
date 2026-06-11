# SPDX-License-Identifier: LGPL-3.0-only
"""maintenance.equipment extension — back-link to tool assets."""
from odoo import _, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    southbrook_tool_asset_ids = fields.One2many(
        "southbrook.tool.asset",
        "equipment_id",
        string="Southbrook Tool Assets",
    )
    southbrook_tool_asset_count = fields.Integer(
        compute="_compute_southbrook_tool_asset_count",
        string="# Tool Assets",
    )

    def _compute_southbrook_tool_asset_count(self):
        for rec in self:
            rec.southbrook_tool_asset_count = len(rec.southbrook_tool_asset_ids)

    def action_view_southbrook_tool_assets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tool Assets on %s") % self.name,
            "res_model": "southbrook.tool.asset",
            "view_mode": "kanban,list,form",
            "domain": [("equipment_id", "=", self.id)],
            "context": {"default_equipment_id": self.id},
        }
