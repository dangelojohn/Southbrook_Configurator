# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.workcenter extension — tool requirements + crib + asset back-refs."""
from odoo import _, fields, models


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    southbrook_tool_requirement_ids = fields.One2many(
        "southbrook.workcenter.tool.requirement",
        "workcenter_id",
        string="Tool Requirements",
    )
    southbrook_tool_requirement_count = fields.Integer(
        compute="_compute_southbrook_tool_requirement_count",
        string="# Tool Requirements",
    )

    southbrook_tool_crib_ids = fields.Many2many(
        "southbrook.tool.crib",
        "southbrook_tool_crib_wc_rel",
        "workcenter_id", "crib_id",
        string="Tool Cribs",
    )

    southbrook_tool_asset_ids = fields.One2many(
        "southbrook.tool.asset",
        "workcenter_id",
        string="Tool Assets",
    )
    southbrook_tool_asset_count = fields.Integer(
        compute="_compute_southbrook_tool_asset_count",
        string="# Tool Assets",
    )

    def _compute_southbrook_tool_requirement_count(self):
        for rec in self:
            rec.southbrook_tool_requirement_count = len(
                rec.southbrook_tool_requirement_ids
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
            "domain": [("workcenter_id", "=", self.id)],
            "context": {"default_workcenter_id": self.id},
        }

    def action_view_southbrook_tool_requirements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tool Requirements on %s") % self.name,
            "res_model": "southbrook.workcenter.tool.requirement",
            "view_mode": "list,form",
            "domain": [("workcenter_id", "=", self.id)],
            "context": {"default_workcenter_id": self.id},
        }
