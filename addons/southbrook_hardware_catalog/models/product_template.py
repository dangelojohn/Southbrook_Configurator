# SPDX-License-Identifier: LGPL-3.0-only
"""Hardware-catalog fields on product.template — primary storage.

The variant-aware refactor (Tier 1.2 audit 2026-06-10) moves brand /
category / SKU / spec fields to the TEMPLATE because they're invariant
across finish/size variants of the same physical item. The same fields
remain queryable on product.product via stored related-fields in
product_product.py — no code change needed at the call sites.
"""
from odoo import fields, models

from .product_product import HARDWARE_CATEGORIES


class ProductTemplate(models.Model):
    _inherit = "product.template"

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
        help="Vendor SKU as listed in the Marathon Hardware workbook. "
             "Templates carry the BASE Marathon SKU; per-finish variants "
             "live on the spawned product.product records.",
    )
    x_pricing_pending = fields.Boolean(
        string="Pricing Pending",
        default=False,
        index=True,
    )

    # Physical spec fields — Marathon publishes these on every product
    # page. Empty until populated.
    x_length_mm = fields.Float(string="Length (mm)")
    x_width_mm = fields.Float(string="Width (mm)")
    x_projection_mm = fields.Float(string="Projection (mm)")
    x_diameter_mm = fields.Float(string="Diameter (mm)")
    x_center_to_center_mm = fields.Float(string="Center-to-Center (mm)")
    x_material = fields.Char(string="Material")
    x_lead_time_days = fields.Integer(string="Lead Time (days)")
    x_package_quantity = fields.Integer(string="Package Qty")
    x_marathon_image_url = fields.Char(
        string="Marathon Image URL",
        help="Public Azure CDN URL of the primary product image as "
             "published on marathonhardware.com.",
    )
