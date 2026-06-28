# SPDX-License-Identifier: LGPL-3.0-only
"""product.template extension — kitchen appliance metadata.

Templates flagged `is_kitchen_appliance=True` carry the dimensional
data designers use to lay out a kitchen room. The Module-7 layout
canvas reads these to draw placeholder rectangles before any cabinet
is placed; the configurator's clearance rules consume the
`kitchen_appliance_clearance_mm` value to refuse adjacent cabinet
placements that would violate code (e.g. 30mm beside a stove).

Field naming uses the `kitchen_appliance_` prefix to avoid collision
with the `southbrook_` extensions in southbrook_estimating
(southbrook_category/_description) and the `x_hardware_` extensions
in southbrook_hardware_catalog (x_hardware_category/_brand_id).
"""
from odoo import fields, models


APPLIANCE_TYPE_SELECTION = [
    # Cooking
    ("range", "Range (Cooktop + Oven)"),
    ("cooktop", "Cooktop"),
    ("wall_oven", "Wall Oven"),
    ("wall_oven_double", "Double Wall Oven"),
    ("microwave", "Microwave"),
    ("steam_oven", "Steam Oven"),
    ("speed_oven", "Speed Oven"),
    ("warming_drawer", "Warming Drawer"),
    ("range_hood", "Range Hood / Ventilation"),
    # Cold
    ("refrigerator", "Refrigerator"),
    ("freezer", "Freezer"),
    ("refrigerator_drawer", "Refrigerator Drawer"),
    ("wine_fridge", "Wine Refrigerator"),
    ("beverage_center", "Beverage Center"),
    ("ice_maker", "Ice Maker"),
    # Cleanup
    ("dishwasher", "Dishwasher"),
    ("sink", "Sink"),
    ("disposal", "Garbage Disposal"),
    ("trash_compactor", "Trash Compactor"),
    # Beverage / specialty
    ("coffee_built_in", "Built-In Coffee Machine"),
    # Catch-all
    ("other", "Other"),
]


INSTALL_TYPE_SELECTION = [
    ("freestanding", "Freestanding"),
    ("slide_in", "Slide-In"),
    ("drop_in", "Drop-In"),
    ("built_in", "Built-In"),
    ("panel_ready", "Panel-Ready (Integrated)"),
    ("undercounter", "Undercounter"),
    ("drawer", "Drawer"),
    ("otr", "Over-The-Range"),
    ("wall_mount", "Wall-Mount"),
    ("undercabinet", "Undercabinet"),
    ("island", "Island"),
    ("downdraft", "Downdraft"),
    ("insert", "Insert (Custom Hood)"),
    ("counter_depth", "Counter-Depth"),
    ("column", "Column"),
    ("integrated", "Integrated (Fully)"),
    ("apron_front", "Apron-Front / Farmhouse"),
    ("undermount", "Undermount"),
    ("top_mount", "Top-Mount"),
    ("workstation", "Workstation"),
    ("other", "Other"),
]


FUEL_TYPE_SELECTION = [
    ("gas", "Gas (Natural)"),
    ("propane", "Propane / LP"),
    ("electric", "Electric (Smoothtop)"),
    ("electric_coil", "Electric (Coil)"),
    ("induction", "Induction"),
    ("dual_fuel", "Dual Fuel (Gas + Electric)"),
    ("na", "Not Applicable"),
]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_kitchen_appliance = fields.Boolean(
        string="Kitchen Appliance",
        index=True,
        help="Mark this product as a kitchen appliance template. Templates "
             "flagged here are pickable from the kitchen project's "
             "Add-Appliance action and their dimensions auto-fill onto "
             "the placed sb.kitchen.appliance record.",
    )
    kitchen_appliance_type = fields.Selection(
        APPLIANCE_TYPE_SELECTION,
        string="Appliance Type",
    )
    kitchen_appliance_install_type = fields.Selection(
        INSTALL_TYPE_SELECTION,
        string="Install Type",
    )
    kitchen_appliance_fuel_type = fields.Selection(
        FUEL_TYPE_SELECTION,
        string="Fuel Type",
        default="na",
    )
    kitchen_appliance_width_mm = fields.Float(
        string="Appliance Width (mm)",
        digits=(8, 1),
    )
    kitchen_appliance_depth_mm = fields.Float(
        string="Appliance Depth (mm)",
        digits=(8, 1),
    )
    kitchen_appliance_height_mm = fields.Float(
        string="Appliance Height (mm)",
        digits=(8, 1),
    )
    kitchen_appliance_clearance_mm = fields.Float(
        string="Required Clearance (mm)",
        digits=(8, 1),
        help="Minimum gap to adjacent cabinets / combustibles. Gas ranges "
             "typically 30-36mm side and 760-910mm above; induction 24-30 "
             "above; sink 0mm.",
    )
