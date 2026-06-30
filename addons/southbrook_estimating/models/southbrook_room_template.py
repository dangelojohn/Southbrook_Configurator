# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room.template — pre-configured room layouts the wizard
can clone in one click. JSON-encoded walls + constraints to keep the
schema flat (Phase 6.2 of Room-First UX).
"""
from odoo import fields, models
from .southbrook_room import _ROOM_TYPES, _LAYOUT_SHAPES


class SouthbrookRoomTemplate(models.Model):
    _name = "southbrook.room.template"
    _description = "Southbrook Room Template"
    _order = "sequence, id"
    _rec_name = "name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text()
    room_type = fields.Selection(_ROOM_TYPES, default="kitchen")
    layout_shape = fields.Selection(_LAYOUT_SHAPES)
    ceiling_height_mm = fields.Integer(default=2400)
    # JSON-serialized walls: [{name, length_mm, wall_order}, ...]
    walls_json = fields.Text(default="[]")
    # JSON-serialized constraints:
    #   [{wall_index, constraint_type, distance_from_left_mm,
    #     width_mm, height_mm}, ...]
    # wall_index references the position in walls_json.
    constraints_json = fields.Text(default="[]")
