# SPDX-License-Identifier: LGPL-3.0-only
"""sb.kitchen.appliance — appliances present in the kitchen room.

The configurator's clearance rules (Rule 7 family region) refuse to
place adjacent cabinets when an appliance's clearance is violated, so
the dimensions on these records ARE load-bearing for downstream
placement decisions. confirmed_by_human gates that path.

2026-06-28 — appliances can now be backed by a product.template flagged
`is_kitchen_appliance=True`. Picking one snapshots dimensions onto the
placed record (snapshot — not related — so a future product-edit
doesn't retroactively change a placed appliance)."""
from odoo import api, fields, models

# Legacy 8-key selection retained for backward compat with existing
# sb.kitchen.appliance records. New product-backed appliances map their
# product.template's kitchen_appliance_type onto this LEGACY_TYPE_MAP.
APPLIANCE_TYPES = [
    ("stove", "Stove / Range"),
    ("fridge", "Refrigerator"),
    ("dishwasher", "Dishwasher"),
    ("sink", "Sink"),
    ("microwave", "Microwave"),
    ("oven_wall", "Wall Oven"),
    ("hood", "Range Hood"),
    ("other", "Other"),
]

LEGACY_TYPE_MAP = {
    "range": "stove",
    "cooktop": "stove",
    "wall_oven": "oven_wall",
    "wall_oven_double": "oven_wall",
    "microwave": "microwave",
    "steam_oven": "oven_wall",
    "speed_oven": "oven_wall",
    "warming_drawer": "other",
    "range_hood": "hood",
    "refrigerator": "fridge",
    "freezer": "fridge",
    "refrigerator_drawer": "fridge",
    "wine_fridge": "fridge",
    "beverage_center": "fridge",
    "ice_maker": "fridge",
    "dishwasher": "dishwasher",
    "sink": "sink",
    "disposal": "other",
    "trash_compactor": "other",
    "coffee_built_in": "other",
    "other": "other",
}


class SbKitchenAppliance(models.Model):
    _name = "sb.kitchen.appliance"
    _description = "Southbrook Kitchen Appliance"
    _order = "project_id, sequence, id"

    project_id = fields.Many2one(
        "sb.kitchen.project", required=True, ondelete="cascade", index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    appliance_type = fields.Selection(APPLIANCE_TYPES, required=True)

    product_id = fields.Many2one(
        comodel_name="product.template",
        string="Appliance Template",
        domain=[("is_kitchen_appliance", "=", True)],
        index=True,
        help="Pick a catalog appliance to auto-fill type + dimensions + "
             "clearance. Leaving blank lets you enter custom dimensions "
             "(e.g. a one-off appliance the customer already owns).",
    )

    width_mm = fields.Float(digits=(8, 1))
    height_mm = fields.Float(digits=(8, 1))
    depth_mm = fields.Float(digits=(8, 1))
    requires_clearance_mm = fields.Integer(
        string="Required Clearance (mm)",
        help="Minimum gap to adjacent cabinets. Stove + dishwasher typical "
             "30 mm; fridge 50 mm; sink 0 mm (cabinet-flanked).",
    )

    # Relative position in the kitchen run, 0.0..1.0 along the wall.
    # 2D layout — y is the depth axis (0=against wall, 1=towards center).
    position_x = fields.Float(digits=(6, 4))
    position_y = fields.Float(digits=(6, 4))

    confirmed_by_human = fields.Boolean(
        help="When False the appliance's dimensions are Gemini-estimates "
             "(GAP-02). Downstream consumers (config engine) refuse to "
             "place cabinets near unconfirmed appliances.",
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            tmpl = rec.product_id
            if not tmpl:
                continue
            if not rec.name:
                rec.name = tmpl.display_name
            if tmpl.kitchen_appliance_type:
                rec.appliance_type = LEGACY_TYPE_MAP.get(
                    tmpl.kitchen_appliance_type, "other",
                )
            if tmpl.kitchen_appliance_width_mm:
                rec.width_mm = tmpl.kitchen_appliance_width_mm
            if tmpl.kitchen_appliance_depth_mm:
                rec.depth_mm = tmpl.kitchen_appliance_depth_mm
            if tmpl.kitchen_appliance_height_mm:
                rec.height_mm = tmpl.kitchen_appliance_height_mm
            if tmpl.kitchen_appliance_clearance_mm:
                rec.requires_clearance_mm = int(
                    tmpl.kitchen_appliance_clearance_mm,
                )
