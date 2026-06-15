# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class InstantiateFromTemplate(models.TransientModel):
    _name = "kitchenforge.instantiate.wizard"
    _description = "Instantiate a Kitchen Project from a Template"

    template_id = fields.Many2one(
        "project.project",
        string="Template",
        domain="[('is_template','=',True)]",
        required=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
    )
    room_width_mm = fields.Integer(string="Room Width (mm)")
    room_depth_mm = fields.Integer(string="Room Depth (mm)")
    ceiling_height_mm = fields.Integer(string="Ceiling Height (mm)", default=2440)
    target_handover_date = fields.Date(string="Target Handover")
    preview_zone_count = fields.Integer(
        compute="_compute_preview_zone_count", string="Zones in Template")

    @api.depends("template_id")
    def _compute_preview_zone_count(self):
        for rec in self:
            rec.preview_zone_count = len(rec.template_id.default_cabinet_zone_ids)

    def action_instantiate(self):
        self.ensure_one()
        if not self.template_id:
            raise UserError(_("Pick a template first."))
        dims = {
            "room_width_mm": self.room_width_mm,
            "room_depth_mm": self.room_depth_mm,
            "ceiling_height_mm": self.ceiling_height_mm,
        }
        new_proj = self.template_id.kitchenforge_instantiate(
            partner=self.partner_id,
            dims=dims,
            target_date=self.target_handover_date,
            origin_channel="backend-wizard",
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Quote: %s") % new_proj.sale_order_id.name,
            "res_model": "sale.order",
            "res_id": new_proj.sale_order_id.id,
            "view_mode": "form",
            "target": "current",
        }
