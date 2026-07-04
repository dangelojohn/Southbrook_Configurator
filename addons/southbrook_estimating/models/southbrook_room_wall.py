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

    # Constraint-geometry conflict sub-flags (2026-07-03 QA fix). Split
    # out of the single has_conflicts so the summary can tell the user
    # WHICH geometry problem a wall has, and so the wizard's inline
    # validator (client) and the /room save endpoints (server, source of
    # truth) share one definition of "out of bounds" / "overlap".
    #   - out_of_bounds: a constraint whose span (distance..distance+width)
    #     leaves the wall (< 0 or > length). BLOCKED at save time.
    #   - overlap: two constraints on the same wall whose spans intersect.
    #     WARNED only (a sink under a window is a real-world possibility),
    #     surfaced here so "No conflicts detected" stops lying.
    has_constraint_out_of_bounds = fields.Boolean(
        compute="_compute_conflicts", store=False)
    has_constraint_overlap = fields.Boolean(
        compute="_compute_conflicts", store=False)

    # ------------------------------------------------------------------
    # Room-First UX Phase 1.2 — reverse O2m + capacity / conflict computes.
    # ------------------------------------------------------------------
    cabinet_line_ids = fields.One2many(
        "sale.order.line", "wall_id", string="Cabinet Lines")
    used_mm = fields.Integer(
        compute="_compute_capacity", store=False, string="Used (mm)")
    remaining_mm = fields.Integer(
        compute="_compute_capacity", store=False, string="Remaining (mm)")
    has_conflicts = fields.Boolean(
        compute="_compute_conflicts", store=False)

    # sb_width_mm is itself a non-stored compute on sale.order.line that
    # also depends on `name` (line free-text). Capacity recomputes when
    # sb_width_mm's SOURCE fields move (product_id, PTAVs, qty) but NOT
    # on line.name edits alone — acceptable since names are only edited
    # interactively for demo-seed lines.
    @api.depends("cabinet_line_ids.sb_width_mm", "cabinet_line_ids.product_uom_qty", "length_mm")
    def _compute_capacity(self):
        for rec in self:
            used = 0.0
            for line in rec.cabinet_line_ids:
                qty = line.product_uom_qty or 0.0
                used += (line.sb_width_mm or 0.0) * qty
            rec.used_mm = int(round(used))
            rec.remaining_mm = (rec.length_mm or 0) - rec.used_mm

    # O2m membership (`cabinet_line_ids`) implicitly invalidates when a
    # line's wall_id changes — listing it as a separate depends entry is
    # redundant. Payload fields below are what actually drive recompute.
    @api.depends(
        "cabinet_line_ids",
        "cabinet_line_ids.position_from_left_mm",
        "cabinet_line_ids.sb_width_mm",
        "length_mm",
        "constraint_ids.distance_from_left_mm",
        "constraint_ids.width_mm",
        "constraint_ids.constraint_type",
    )
    def _compute_conflicts(self):
        for rec in self:
            length = rec.length_mm or 0
            # ranges = "blocking" constraint spans (things a cabinet must
            # not collide with). power_outlet / structural_post are point
            # markers, not cabinet-blocking, so they're excluded from the
            # cabinet-collision AND the overlap checks below.
            ranges = []
            oob = False
            for c in rec.constraint_ids:
                start = c.distance_from_left_mm or 0
                width = c.width_mm or 0
                # Out-of-bounds: the constraint leaves the wall. width==0
                # markers (a power point) only fail if placed off the end.
                if start < 0 or start + width > length:
                    oob = True
                if width and c.constraint_type not in ("power_outlet", "structural_post"):
                    ranges.append((start, start + width))
            # Constraint-vs-constraint overlap on the same wall.
            overlap = False
            for i in range(len(ranges)):
                a0, a1 = ranges[i]
                for j in range(i + 1, len(ranges)):
                    b0, b1 = ranges[j]
                    if a0 < b1 and a1 > b0:
                        overlap = True
                        break
                if overlap:
                    break
            # Cabinet-vs-constraint collision (original behaviour).
            cab_conflict = False
            for line in rec.cabinet_line_ids:
                if line.position_from_left_mm is False or not line.sb_width_mm:
                    continue
                lo = line.position_from_left_mm or 0
                hi = lo + int(line.sb_width_mm)
                for clo, chi in ranges:
                    if lo < chi and hi > clo:
                        cab_conflict = True
                        break
                if cab_conflict:
                    break
            rec.has_constraint_out_of_bounds = oob
            rec.has_constraint_overlap = overlap
            rec.has_conflicts = cab_conflict or oob or overlap
