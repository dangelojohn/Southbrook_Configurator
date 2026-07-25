# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    material_id = fields.Many2one(
        "southbrook.kitchen.material", string="Material",
        help="Physical material this attribute value resolves to.")


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _resolve_material(self):
        """Return the southbrook.kitchen.material for this variant via its
        'Material' attribute value, else empty recordset."""
        self.ensure_one()
        vals = self.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id").filtered("material_id")
        return vals[:1].material_id
