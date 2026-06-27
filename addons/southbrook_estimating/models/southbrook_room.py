# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room — first-class room anchoring an order to a physical space.

Per the Room-First UX initiative (2026-06-27): every order can optionally
declare one room (multi-room support planned via the O2m from sale.order
keeping the migration cost low). Wall + constraint child models live in
sibling files.
"""
from odoo import api, fields, models


_ROOM_TYPES = [
    ("kitchen", "Kitchen"),
    ("laundry", "Laundry"),
    ("butler", "Butler's Pantry"),
    ("bar", "Bar"),
    ("bathroom", "Bathroom"),
    ("office", "Office"),
    ("other", "Other"),
]

_LAYOUT_SHAPES = [
    ("straight", "Straight"),
    ("l_shape", "L-Shape"),
    ("u_shape", "U-Shape"),
    ("galley", "Galley"),
    ("g_shape", "G-Shape"),
    ("island", "Island"),
    ("peninsula", "Peninsula"),
    ("custom", "Custom"),
]

_UNIT_PREF = [("mm", "Millimetres"), ("imperial", "Feet & Inches")]


class SouthbrookRoom(models.Model):
    _name = "southbrook.room"
    _description = "Southbrook Room"
    _order = "id desc"
    _rec_name = "name"

    name = fields.Char(required=True, default="Main Kitchen")
    order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade", index=True,
        help="The Sale Order this room belongs to.")

    room_type = fields.Selection(_ROOM_TYPES, default="kitchen")
    layout_shape = fields.Selection(_LAYOUT_SHAPES)
    ceiling_height_mm = fields.Integer(default=2400, string="Ceiling Height (mm)")
    unit_preference = fields.Selection(
        _UNIT_PREF, default="mm", required=True,
        help="Drives display across the whole order. Storage is always mm.")

    wall_ids = fields.One2many(
        "southbrook.room.wall", "room_id", string="Walls")
    constraint_ids = fields.One2many(
        "southbrook.room.constraint", "room_id", string="Constraints")

    total_linear_mm = fields.Integer(
        compute="_compute_summary", store=True, string="Total Linear (mm)")
    wall_count = fields.Integer(compute="_compute_summary", store=True)
    constraint_count = fields.Integer(compute="_compute_summary", store=True)
    layout_complete = fields.Boolean(compute="_compute_summary", store=True)
    has_plumbing = fields.Boolean(compute="_compute_summary", store=True)

    @api.depends(
        "layout_shape", "wall_ids", "wall_ids.length_mm",
        "constraint_ids", "constraint_ids.constraint_type",
    )
    def _compute_summary(self):
        plumbing = {"sink", "dishwasher"}
        for rec in self:
            walls = rec.wall_ids
            rec.wall_count = len(walls)
            rec.total_linear_mm = sum(w.length_mm or 0 for w in walls)
            rec.constraint_count = len(rec.constraint_ids)
            positive = [w for w in walls if (w.length_mm or 0) > 0]
            single_wall_shapes = {"straight", "island"}
            min_walls = 1 if rec.layout_shape in single_wall_shapes else 2
            rec.layout_complete = bool(
                rec.layout_shape and len(positive) >= min_walls)
            rec.has_plumbing = any(
                c.constraint_type in plumbing for c in rec.constraint_ids)
