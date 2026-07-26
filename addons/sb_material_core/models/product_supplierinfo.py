# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class ProductSupplierinfo(models.Model):
    _inherit = "product.supplierinfo"

    uom_yield_qty = fields.Float(
        string="Yield per Purchase Unit",
        digits=(12, 4),
        default=0.0,
        help="How much material (in the material's canonical demand unit — "
             "m² for sheet/area goods, linear m for edgebanding) one purchase "
             "unit yields. Example: a 4'×8' sheet yields ~2.97 m². Used to "
             "convert consumption demand into a suggested purchase quantity. "
             "0 = not recorded (no suggestion produced).",
    )
