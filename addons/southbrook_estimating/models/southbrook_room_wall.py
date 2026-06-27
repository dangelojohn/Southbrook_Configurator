# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room.wall — one wall of a room with its own cabinet zones."""
from odoo import api, fields, models


class SouthbrookRoomWall(models.Model):
    _name = "southbrook.room.wall"
    _description = "Southbrook Room Wall"
    _order = "room_id, wall_order, id"
    _rec_name = "name"

    name = fields.Char(required=True, default="Wall A")
    room_id = fields.Many2one(
        "southbrook.room", required=True, ondelete="cascade", index=True)
    order_id = fields.Many2one(
        "sale.order", related="room_id.order_id", store=True, index=True)

    length_mm = fields.Integer(string="Length (mm)", default=0)
    wall_order = fields.Integer(default=10)

    has_upper_cabinets = fields.Boolean(default=True)
    has_base_cabinets = fields.Boolean(default=True)
    has_tall_cabinets = fields.Boolean(default=False)

    constraint_ids = fields.One2many(
        "southbrook.room.constraint", "wall_id", string="Constraints")
    # Reverse O2m + capacity computes are populated by Task 1.2.
