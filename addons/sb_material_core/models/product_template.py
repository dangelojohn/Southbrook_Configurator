# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    material_id = fields.Many2one(
        "southbrook.kitchen.material", string="Material (Southbrook)",
        help="Fallback material for this product when no variant attribute "
             "value resolves one (product.product._resolve_material()). "
             "Used mainly for plain BoM component products (e.g. sheet "
             "goods) that carry no Material attribute of their own.")
