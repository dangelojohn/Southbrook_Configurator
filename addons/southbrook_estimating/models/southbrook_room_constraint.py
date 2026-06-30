# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room.constraint — a fixed obstacle/feature pinned to a wall."""
from odoo import fields, models


_CONSTRAINT_TYPES = [
    ("window", "Window"),
    ("door", "Door"),
    ("sink", "Sink"),
    ("cooktop", "Cooktop"),
    ("oven", "Oven"),
    ("dishwasher", "Dishwasher"),
    ("rangehood", "Rangehood"),
    ("fridge_space", "Fridge Space"),
    ("power_outlet", "Power Outlet"),
    ("structural_post", "Structural Post"),
    ("other", "Other"),
]


class SouthbrookRoomConstraint(models.Model):
    _name = "southbrook.room.constraint"
    _description = "Southbrook Room Constraint"
    _order = "wall_id, distance_from_left_mm, id"

    constraint_type = fields.Selection(_CONSTRAINT_TYPES, required=True, default="window")
    wall_id = fields.Many2one(
        "southbrook.room.wall", required=True, ondelete="cascade", index=True)
    room_id = fields.Many2one(
        "southbrook.room", related="wall_id.room_id", store=True, index=True)

    distance_from_left_mm = fields.Integer(default=0)
    width_mm = fields.Integer(default=0)
    height_mm = fields.Integer(default=0)
    height_from_floor_mm = fields.Integer(default=0)
    notes = fields.Text()
