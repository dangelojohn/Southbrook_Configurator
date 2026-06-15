# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo import _, api, fields, models


class TemplateLine(models.Model):
    """A cabinet zone pre-seeded on a project template.

    On instantiation, each line becomes one sale.order.line, carrying the
    configurator attribute pre-selections (box material, door style, etc.)
    so the salesperson opens to a working quote rather than 11 wizard
    steps per cabinet.
    """

    _name = "kitchenforge.template.line"
    _description = "KitchenForge Template Cabinet Zone"
    _order = "sequence, id"

    template_project_id = fields.Many2one(
        "project.project",
        string="Template Project",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(
        required=True,
        help="Label of the cabinet zone, e.g. 'B-01 Sink Base 36\"'.")
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Cabinet Template",
        required=True,
        domain="[('config_ok','=',True)]",
        help="Configurable cabinet template (config_ok=True).",
    )
    quantity = fields.Float(default=1.0)
    width_mm = fields.Integer(default=600)
    height_mm = fields.Integer(default=720)
    depth_mm = fields.Integer(default=580)
    preselected_attribute_values_json = fields.Text(
        string="Preselected Attribute Values (JSON)",
        default="{}",
        help="Dict: { product.attribute.id: product.attribute.value.id }. "
             "Loaded into the configurator session at instantiation so the "
             "line lands on the SO with a real variant, not a stub.",
    )
    notes = fields.Char()

    def _to_so_line_vals(self, dims=None):
        """Convert template line -> sale.order.line vals."""
        self.ensure_one()
        product = self.product_tmpl_id.product_variant_id
        name = f"{self.name} ({self.product_tmpl_id.name})"
        return {
            "product_id": product.id,
            "name": name,
            "product_uom_qty": self.quantity,
            "kitchenforge_template_line_id": self.id,
            "kitchenforge_zone_width_mm": self.width_mm,
            "kitchenforge_zone_height_mm": self.height_mm,
            "kitchenforge_zone_depth_mm": self.depth_mm,
            "kitchenforge_preselected_attrs_json": self.preselected_attribute_values_json,
        }

    @api.constrains("preselected_attribute_values_json")
    def _check_preselected_json(self):
        for rec in self:
            if not rec.preselected_attribute_values_json:
                continue
            try:
                payload = json.loads(rec.preselected_attribute_values_json)
                if not isinstance(payload, dict):
                    raise ValueError("must be a JSON object")
            except (ValueError, TypeError) as exc:
                from odoo.exceptions import ValidationError
                raise ValidationError(
                    _("Preselected attribute values must be a JSON object "
                      "mapping attribute_id -> value_id. Got: %s") % exc) from exc
