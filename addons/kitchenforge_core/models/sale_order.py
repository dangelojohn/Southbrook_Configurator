# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    kitchenforge_template_id = fields.Many2one(
        "project.project",
        string="KitchenForge Template",
        domain="[('is_template','=',True)]",
        index=True,
        readonly=True,
    )
    kitchenforge_project_id = fields.Many2one(
        "project.project",
        string="KitchenForge Project",
        index=True,
        readonly=True,
    )


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    kitchenforge_template_line_id = fields.Many2one(
        "kitchenforge.template.line",
        string="Template Zone",
        index=True,
        readonly=True,
    )
    kitchenforge_zone_width_mm = fields.Integer()
    kitchenforge_zone_height_mm = fields.Integer()
    kitchenforge_zone_depth_mm = fields.Integer()
    kitchenforge_preselected_attrs_json = fields.Text()
