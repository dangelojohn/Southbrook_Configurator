# SPDX-License-Identifier: LGPL-3.0-only
"""Additive hardware-catalog fields on product.product."""
from odoo import fields, models


HARDWARE_CATEGORIES = [
    ("hinge", "Hinge"),
    ("slide", "Drawer Slide"),
    ("pin", "Shelf Pin"),
    ("screw", "Screw / Fastener"),
    ("handle", "Handle / Pull"),
    ("leveler", "Cabinet Leveler"),
    ("cam_lock", "Cam Lock / RTA"),
    ("bumper", "Bumper / Stop"),
    ("other", "Other"),
]


class ProductProduct(models.Model):
    _inherit = "product.product"

    x_hardware_category = fields.Selection(
        HARDWARE_CATEGORIES,
        string="Hardware Category",
        help="Sets which slot in the hardware-resolution map this SKU "
             "occupies. Leave blank for non-hardware products.",
    )
    x_hardware_brand_id = fields.Many2one(
        comodel_name="southbrook.hardware.brand",
        string="Brand",
        ondelete="restrict",
    )
    x_marathon_sku = fields.Char(
        string="Marathon SKU",
        index=True,
        help="Vendor SKU as listed in the Marathon Hardware workbook.",
    )
    x_pricing_pending = fields.Boolean(
        string="Pricing Pending",
        default=False,
        index=True,
        help="Set when cost/price requires trade-account login and is not "
             "yet resolved. The configurator can still pick this SKU; the "
             "BoM shows it but the line price is zero until resolved.",
    )
