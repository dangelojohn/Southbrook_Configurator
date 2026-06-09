# SPDX-License-Identifier: LGPL-3.0-only
"""sb.kitchen.appliance — appliances present in the kitchen room.

The configurator's clearance rules (Rule 7 family region) refuse to
place adjacent cabinets when an appliance's clearance is violated, so
the dimensions on these records ARE load-bearing for downstream
placement decisions. confirmed_by_human gates that path."""
from odoo import fields, models


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
