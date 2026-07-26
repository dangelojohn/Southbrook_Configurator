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
        """Return the southbrook.kitchen.material for this variant.

        Precedence (unchanged from before Repair Wave 3, attribute path
        first):
        1. The 'Material' attribute value on this variant, if any attribute
           value carries one.
        2. Wave 3 fallback: `self.product_tmpl_id.material_id`, for plain
           component products (e.g. sheet goods) that carry no attributes
           at all — every BoM component product needs SOME way to resolve
           a material, not just configurable cabinet variants.
        3. Neither set -> empty recordset (honesty contract: never
           fabricate a material).
        """
        self.ensure_one()
        vals = self.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id").filtered("material_id")
        if vals:
            return vals[:1].material_id
        return self.product_tmpl_id.material_id
