# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room — first-class room anchoring an order to a physical space.

Per the Room-First UX initiative (2026-06-27): every order can optionally
declare one room (multi-room support planned via the O2m from sale.order
keeping the migration cost low). Wall + constraint child models live in
sibling files.
"""
import html
import math

from markupsafe import Markup

from odoo import api, fields, models


_ROOM_TYPES = [
    ("kitchen", "Kitchen"),
    ("laundry", "Laundry"),
    ("butler", "Butler's Pantry"),
    ("bar", "Bar"),
    ("bathroom", "Bathroom"),
    # Bath / mudroom / closet aliases the wizard exposes — added so the
    # Phase 2.C tiles can submit cleanly without server validation
    # rejecting the value as outside the Selection set.
    ("bath", "Bath"),
    ("mudroom", "Mudroom"),
    ("closet", "Closet"),
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


# Phase 5 — human labels for QWeb consumption. Kept explicit (not derived
# from the Selection metadata at runtime) so the Customer Spec Sheet PDF
# template can rely on a stable label map even if the Selection options
# are later renamed for UI clarity.
_SHAPE_LABELS = {
    "straight": "Straight",
    "l_shape": "L-Shape",
    "u_shape": "U-Shape",
    "galley": "Galley",
    "g_shape": "G-Shape",
    "island": "Island",
    "peninsula": "Peninsula",
    "custom": "Custom",
}

_CONSTRAINT_LABELS = {
    "window": "Window",
    "door": "Door",
    "sink": "Sink",
    "cooktop": "Cooktop",
    "oven": "Oven",
    "dishwasher": "Dishwasher",
    "rangehood": "Rangehood",
    "fridge_space": "Fridge Space",
    "power_outlet": "Power Outlet",
    "structural_post": "Structural Post",
    "other": "Other",
}

# Phase 5 — constraint colour palette for the PDF floor plan. Hex literals
# (NOT CSS custom properties) — wkhtmltopdf's WebKit doesn't resolve
# `var(--sb-*)`. Mirrors the on-screen Room Layout palette.
_CONSTRAINT_COLORS = {
    "window": "#5E8FBE",       # Sky
    "sink": "#C28840",         # Warn
    "dishwasher": "#C28840",
    "oven": "#A03E2D",         # Alert
    "cooktop": "#A03E2D",
    "rangehood": "#A03E2D",
    "door": "#776B5C",         # Ink-dim
    "fridge_space": "#776B5C",
    "power_outlet": "#776B5C",
    "structural_post": "#776B5C",
    "other": "#776B5C",
}

_ZONE_COLORS = {
    "base_run":  "#D6B98A",
    "wall":      "#EAE0CB",
    "tall":      "#5B4A3A",
    "island":    "#9CC0E2",
    "accessory": "#E0C7A0",
    "other":     "#C9C0B2",
}

_DEFAULT_GALLEY_GAP_MM = 1200


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

    # M3 (2026-07-06) — visibility for cabinets on the order that aren't
    # yet placed on a wall. wall.used_mm only counts sale.order.line rows
    # whose wall_id is set (the Room Layout drag UI assigns it), so
    # cabinets added straight into the Order Lines tab are invisible to
    # per-wall capacity and every wall reads "0 used (mm)" even though the
    # order has cabinets. This surfaces the count so "0 used" is no longer
    # misleading — the rep can see N cabinets still need placing on a wall.
    unplaced_cabinet_count = fields.Integer(
        compute="_compute_unplaced_cabinets", store=False,
        string="Cabinets not yet placed on a wall")

    @api.depends(
        "order_id.order_line",
        "order_id.order_line.wall_id",
        "order_id.order_line.product_uom_qty",
    )
    def _compute_unplaced_cabinets(self):
        for rec in self:
            count = 0
            for line in (rec.order_id.order_line if rec.order_id else []):
                tmpl = line.product_id.product_tmpl_id
                # southbrook_is_cabinet flags configurable cabinet products;
                # read (not depend) since it effectively never changes.
                if (tmpl and getattr(tmpl, "southbrook_is_cabinet", False)
                        and not line.wall_id):
                    count += 1
            rec.unplaced_cabinet_count = count

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

    # ------------------------------------------------------------------
    # Geometry validation (2026-07-03 QA fix). Shared source-of-truth
    # for the /room/create + /room/update controllers. The wizard runs a
    # mirror of these rules client-side for instant feedback, but the
    # server is authoritative: a hand-crafted curl (or a stale client)
    # can never persist a negative length or an off-the-wall constraint.
    #
    # Returns a list of human-readable BLOCKING error strings (empty ==
    # valid). Overlaps are intentionally NOT blocking — they're a real
    # possibility (a sink beneath a window) and are surfaced as a warning
    # via wall.has_constraint_overlap instead of rejected here.
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_int(value, default=0):
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_dim(value):
        """Parse a dimension to int mm. Empty/None → 0 (an omitted field);
        a non-numeric value → None so the caller flags it as an error
        rather than silently coercing to 0 (the server is the source of
        truth — a bypassed client must not persist a zero-size fixture)."""
        if value in (None, ""):
            return 0
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    @classmethod
    def validate_geometry(cls, walls_payload, constraints_payload=None,
                          ceiling_height_mm=None):
        """Validate a wizard payload. `walls_payload` is a list of dicts
        each with `length_mm`; `constraints_payload` a list of dicts with
        `wall_index`, `distance_from_left_mm`, `width_mm`. Non-numeric or
        negative dimensions are errors (never silently coerced on the
        server — the client already clamps, so a negative reaching here
        means a bypassed client)."""
        errors = []
        walls_payload = walls_payload or []
        constraints_payload = constraints_payload or []

        if ceiling_height_mm is not None:
            ch = cls._coerce_int(ceiling_height_mm, default=-1)
            if ch < 0:
                errors.append("Ceiling height must be zero or positive.")

        wall_lengths = []
        for idx, w in enumerate(walls_payload):
            raw = w.get("length_mm")
            length = cls._coerce_int(raw, default=-1)
            if raw not in (None, "") and length < 0:
                errors.append(
                    f"Wall {chr(ord('A') + idx)} length must be zero or "
                    f"positive.")
            wall_lengths.append(max(0, length))

        for cidx, c in enumerate(constraints_payload):
            wi = c.get("wall_index")
            start = cls._parse_dim(c.get("distance_from_left_mm"))
            width = cls._parse_dim(c.get("width_mm"))
            if start is None:
                errors.append(
                    f"Constraint {cidx + 1}: distance from left must be a "
                    f"number.")
                start = 0
            elif start < 0:
                errors.append(
                    f"Constraint {cidx + 1}: distance from left cannot be "
                    f"negative.")
            if width is None:
                errors.append(
                    f"Constraint {cidx + 1}: width must be a number.")
                width = 0
            elif width < 0:
                errors.append(
                    f"Constraint {cidx + 1}: width cannot be negative.")
            if isinstance(wi, int) and 0 <= wi < len(wall_lengths):
                wall_len = wall_lengths[wi]
                if wall_len and start + max(0, width) > wall_len:
                    errors.append(
                        f"Constraint {cidx + 1} on Wall "
                        f"{chr(ord('A') + wi)} extends "
                        f"{start + max(0, width) - wall_len}mm past the wall "
                        f"edge.")
        return errors

    # ------------------------------------------------------------------
    # Phase 5 — QWeb-friendly helpers for the Customer Spec Sheet PDF
    # (rooms page + floor-plan page). The helpers also feed any future
    # API surface that wants a snapshot of the configured room.
    # ------------------------------------------------------------------

    def to_summary_dict(self):
        """Plain-dict snapshot of this room for QWeb consumption.

        Returns a JSON-serialisable structure. Field shape is locked by
        the Phase 5 spec; keep it stable for QWeb compatibility.
        """
        self.ensure_one()
        rec = self
        walls_sorted = rec.wall_ids.sorted(
            key=lambda x: (x.wall_order, x.id))
        constraints_sorted = rec.constraint_ids.sorted(
            key=lambda x: (x.wall_id.wall_order, x.wall_id.id,
                           x.distance_from_left_mm))
        return {
            "name": rec.name,
            "shape_label": _SHAPE_LABELS.get(rec.layout_shape or "", "—"),
            "ceiling_mm": rec.ceiling_height_mm,
            "unit": rec.unit_preference,
            "total_linear_mm": rec.total_linear_mm,
            "wall_count": rec.wall_count,
            "constraint_count": rec.constraint_count,
            "plumbing": rec.has_plumbing,
            "layout_complete": rec.layout_complete,
            "walls": [
                {
                    "name": w.name,
                    "length_mm": w.length_mm,
                    "used_mm": w.used_mm,
                    "remaining_mm": w.remaining_mm,
                    "conflicts": w.has_conflicts,
                    "conflict_count": w.conflict_count,
                    "constraint_count": len(w.constraint_ids),
                }
                for w in walls_sorted
            ],
            "constraints": [
                {
                    "wall_name": c.wall_id.name,
                    "type_label": _CONSTRAINT_LABELS.get(
                        c.constraint_type or "", "—"),
                    "type_code": c.constraint_type,
                    "position_mm": c.distance_from_left_mm,
                    "width_mm": c.width_mm,
                    "height_mm": c.height_mm,
                }
                for c in constraints_sorted
            ],
        }

    @staticmethod
    def to_imperial_str(mm):
        """Convert mm (int) → \"3' 6\\\"\" string. Drops the feet token
        for sub-foot values."""
        try:
            mm = int(round(float(mm or 0)))
        except (TypeError, ValueError):
            mm = 0
        inches_total = round(mm / 25.4)
        feet, inches = divmod(int(inches_total), 12)
        if feet:
            return f"{feet}' {inches}\""
        return f'{inches}"'

    # ------------------------------------------------------------------
    # SVG floor plan — server-side renderer that mirrors the geometry
    # algorithm in `addons/southbrook_estimating_website/static/src/js/
    # room_geometry.esm.js`. Used by the Customer Spec Sheet PDF.
    #
    # wkhtmltopdf compatibility:
    #   - hex colors only (no `var(--sb-*)`).
    #   - inline `style="font-family: Helvetica, sans-serif"` on <text>
    #     (web fonts don't load in the PDF context).
    #   - no `display:flex` anywhere in the markup.
    # ------------------------------------------------------------------
    def to_svg(self, width_px=720, height_px=540):
        """Return a Markup-wrapped SVG string (with outer <svg> wrapper)
        of the top-down floor plan.

        QA bug (2026-07-04, found while testing the Print action):
        returning a plain str here made the Signature Spec Sheet report
        crash with `KeyError: 'Markup'` — its QWeb template calls
        `t-out="Markup(room.to_svg(...))"`, but `Markup` is only bound
        in ir.qweb's internal compiler globals, not in the expression
        namespace `t-out`/`t-if` strings are evaluated against, so
        referencing it BY NAME inside a template expression fails.
        Returning an already-Markup-wrapped string here (the standard
        Odoo pattern for "trusted, pre-escaped HTML/SVG from Python")
        lets the template just do `t-out="room.to_svg(...)"` with no
        in-template Markup() call needed at all. Safe to trust: every
        user-supplied substring embedded below (wall names, constraint
        labels) is already run through html.escape() before insertion.
        """
        self.ensure_one()
        rec = self

        walls = rec.wall_ids.sorted(key=lambda x: (x.wall_order, x.id))
        if not walls:
            return Markup(
                f'<svg width="{int(width_px)}" height="{int(height_px)}" '
                f'viewBox="0 0 {int(width_px)} {int(height_px)}" '
                f'xmlns="http://www.w3.org/2000/svg">'
                f'<rect width="100%" height="100%" fill="#FAF7EE"/>'
                f'<text x="50%" y="50%" text-anchor="middle" '
                f'style="font-family: Helvetica, sans-serif; font-size: 14px; '
                f'fill: #776B5C;">Room has no walls yet</text>'
                f'</svg>'
            )

        segments = self._wall_segments_for_shape(
            rec.layout_shape, [(w.name or "", int(w.length_mm or 0)) for w in walls])
        if segments is None:
            # Fallback for shapes not yet first-class in geometry helper:
            # stack walls vertically (matches the JS FloorPlanSVG fallback).
            segments = []
            y_cursor = 0
            for w in walls:
                ln = int(w.length_mm or 0)
                segments.append(self._mk_seg(
                    w.name or "", ln, 0, y_cursor, ln, y_cursor, 0, 1))
                y_cursor += 600  # nominal vertical step between stacked walls

        # Pair each segment with its source wall recordset (same order).
        wall_segs = list(zip(walls, segments))

        # --- collect all points for bbox / scale ---
        pts = []
        for _w, s in wall_segs:
            pts.append((s["x0"], s["y0"]))
            pts.append((s["x1"], s["y1"]))

        # Constraints + cabinet polygons add additional points
        # (computed in mm-space) for the scale fit. Inset constraints
        # along the wall normal by their nominal depth (400 mm) so the
        # bbox encloses them.
        constraint_depth_mm = 400
        cabinet_depth_mm = 600
        for w, s in wall_segs:
            for c in w.constraint_ids:
                cstart = (c.distance_from_left_mm or 0)
                cwidth = (c.width_mm or 0)
                p0x = s["x0"] + s["dx"] * cstart
                p0y = s["y0"] + s["dy"] * cstart
                p1x = p0x + s["dx"] * cwidth
                p1y = p0y + s["dy"] * cwidth
                inset_x = s["normalX"] * constraint_depth_mm
                inset_y = s["normalY"] * constraint_depth_mm
                pts.append((p0x, p0y))
                pts.append((p1x + inset_x, p1y + inset_y))
            for line in w.cabinet_line_ids:
                if not line.sb_width_mm:
                    continue
                lo = line.position_from_left_mm or 0
                hi = lo + int(line.sb_width_mm or 0)
                p0x = s["x0"] + s["dx"] * lo
                p0y = s["y0"] + s["dy"] * lo
                p1x = s["x0"] + s["dx"] * hi
                p1y = s["y0"] + s["dy"] * hi
                inset_x = s["normalX"] * cabinet_depth_mm
                inset_y = s["normalY"] * cabinet_depth_mm
                pts.append((p0x, p0y))
                pts.append((p1x + inset_x, p1y + inset_y))

        if not pts:
            pts = [(0, 0), (1, 1)]

        min_x = min(p[0] for p in pts)
        max_x = max(p[0] for p in pts)
        min_y = min(p[1] for p in pts)
        max_y = max(p[1] for p in pts)
        span_x = max(max_x - min_x, 1)
        span_y = max(max_y - min_y, 1)

        pad = 40
        avail_w = max(int(width_px) - pad * 2, 1)
        avail_h = max(int(height_px) - pad * 2, 1)
        scale = min(avail_w / span_x, avail_h / span_y)

        # Centre the drawing in the viewport
        draw_w = span_x * scale
        draw_h = span_y * scale
        offset_x = (int(width_px) - draw_w) / 2 - min_x * scale
        offset_y = (int(height_px) - draw_h) / 2 - min_y * scale

        def _proj(x, y):
            return (x * scale + offset_x, y * scale + offset_y)

        parts = [
            f'<svg width="{int(width_px)}" height="{int(height_px)}" '
            f'viewBox="0 0 {int(width_px)} {int(height_px)}" '
            f'xmlns="http://www.w3.org/2000/svg">',
            # Background — Linen.
            f'<rect width="100%" height="100%" fill="#FAF7EE"/>',
        ]

        # --- Layer 1: gap markers (dashed). Drawn BENEATH cabinets so a
        # placed cabinet visually covers a stale gap marker without a
        # paint-order glitch. ---
        for w, s in wall_segs:
            if not w.cabinet_line_ids:
                continue
            placed = sorted(
                [(line.position_from_left_mm or 0,
                  int(line.sb_width_mm or 0))
                 for line in w.cabinet_line_ids if line.sb_width_mm],
                key=lambda t: t[0])
            length = int(w.length_mm or 0)
            cursor = 0
            for lo, width in placed:
                if lo - cursor >= 200:
                    parts.append(self._dashed_gap_rect(
                        s, cursor, lo - cursor, cabinet_depth_mm, _proj))
                cursor = max(cursor, lo + width)
            if length - cursor >= 200:
                parts.append(self._dashed_gap_rect(
                    s, cursor, length - cursor, cabinet_depth_mm, _proj))

        # --- Layer 2: cabinets. ---
        for w, s in wall_segs:
            conflict = bool(w.has_conflicts)
            for line in w.cabinet_line_ids:
                if not line.sb_width_mm:
                    continue
                lo = line.position_from_left_mm or 0
                width = int(line.sb_width_mm or 0)
                zone = line.zone or "other"
                fill = _ZONE_COLORS.get(zone, _ZONE_COLORS["other"])
                stroke = "#A03E2D" if conflict else "#3D2F22"
                stroke_w = 3 if conflict else 1.5
                # Project four polygon corners.
                p0 = _proj(s["x0"] + s["dx"] * lo,
                           s["y0"] + s["dy"] * lo)
                p1 = _proj(s["x0"] + s["dx"] * (lo + width),
                           s["y0"] + s["dy"] * (lo + width))
                p2 = _proj(s["x0"] + s["dx"] * (lo + width)
                           + s["normalX"] * cabinet_depth_mm,
                           s["y0"] + s["dy"] * (lo + width)
                           + s["normalY"] * cabinet_depth_mm)
                p3 = _proj(s["x0"] + s["dx"] * lo
                           + s["normalX"] * cabinet_depth_mm,
                           s["y0"] + s["dy"] * lo
                           + s["normalY"] * cabinet_depth_mm)
                points_str = (
                    f"{p0[0]:.1f},{p0[1]:.1f} "
                    f"{p1[0]:.1f},{p1[1]:.1f} "
                    f"{p2[0]:.1f},{p2[1]:.1f} "
                    f"{p3[0]:.1f},{p3[1]:.1f}"
                )
                parts.append(
                    f'<polygon points="{points_str}" '
                    f'fill="{fill}" stroke="{stroke}" '
                    f'stroke-width="{stroke_w}"/>'
                )
                # Label — max 8 chars; product.default_code wins over name.
                raw_label = (
                    line.product_id.default_code
                    or line.product_id.display_name
                    or line.name or "")
                label = (raw_label or "")[:8]
                cx = (p0[0] + p1[0] + p2[0] + p3[0]) / 4
                cy = (p0[1] + p1[1] + p2[1] + p3[1]) / 4
                parts.append(
                    f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
                    f'dominant-baseline="central" '
                    f'style="font-family: Helvetica, sans-serif; '
                    f'font-size: 9px; fill: #3D2F22;">'
                    f'{html.escape(label)}</text>'
                )

        # --- Layer 3: constraints. Drawn AFTER cabinets so a window/sink
        # marker stays visible even if its position overlaps a placed
        # cabinet (the conflict-stroke on the cabinet plus the constraint
        # rect together communicate the conflict). ---
        for w, s in wall_segs:
            for c in w.constraint_ids:
                ctype = c.constraint_type or "other"
                fill = _CONSTRAINT_COLORS.get(ctype, _CONSTRAINT_COLORS["other"])
                cstart = c.distance_from_left_mm or 0
                cwidth = c.width_mm or 0
                if cwidth <= 0:
                    continue
                cdepth = constraint_depth_mm
                q0 = _proj(s["x0"] + s["dx"] * cstart,
                           s["y0"] + s["dy"] * cstart)
                q1 = _proj(s["x0"] + s["dx"] * (cstart + cwidth),
                           s["y0"] + s["dy"] * (cstart + cwidth))
                q2 = _proj(s["x0"] + s["dx"] * (cstart + cwidth)
                           + s["normalX"] * cdepth,
                           s["y0"] + s["dy"] * (cstart + cwidth)
                           + s["normalY"] * cdepth)
                q3 = _proj(s["x0"] + s["dx"] * cstart
                           + s["normalX"] * cdepth,
                           s["y0"] + s["dy"] * cstart
                           + s["normalY"] * cdepth)
                points_str = (
                    f"{q0[0]:.1f},{q0[1]:.1f} "
                    f"{q1[0]:.1f},{q1[1]:.1f} "
                    f"{q2[0]:.1f},{q2[1]:.1f} "
                    f"{q3[0]:.1f},{q3[1]:.1f}"
                )
                parts.append(
                    f'<polygon points="{points_str}" fill="{fill}" '
                    f'fill-opacity="0.55" stroke="{fill}" stroke-width="1"/>'
                )
                # Type label above the marker (outward along the normal).
                label = _CONSTRAINT_LABELS.get(ctype, "—")
                lx = (q0[0] + q1[0]) / 2
                ly = (q0[1] + q1[1]) / 2
                parts.append(
                    f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                    f'dy="-4" '
                    f'style="font-family: Helvetica, sans-serif; '
                    f'font-size: 8px; fill: #3D2F22;">'
                    f'{html.escape(label)}</text>'
                )

        # --- Layer 4: wall lines + labels. Drawn last so wall labels
        # stay legible above any rectangles. ---
        for w, s in wall_segs:
            x0, y0 = _proj(s["x0"], s["y0"])
            x1, y1 = _proj(s["x1"], s["y1"])
            parts.append(
                f'<line x1="{x0:.1f}" y1="{y0:.1f}" '
                f'x2="{x1:.1f}" y2="{y1:.1f}" '
                f'stroke="#5B4A3A" stroke-width="6" '
                f'stroke-linecap="round"/>'
            )
            # Wall label at midpoint, offset 18px OUTWARD (opposite of
            # the interior normal).
            mx = (x0 + x1) / 2 - s["normalX"] * 18
            my = (y0 + y1) / 2 - s["normalY"] * 18
            wall_lbl = f"{w.name or ''}  {int(w.length_mm or 0)} mm"
            parts.append(
                f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" '
                f'dominant-baseline="central" '
                f'style="font-family: Helvetica, sans-serif; '
                f'font-size: 10px; fill: #3D2F22;">'
                f'{html.escape(wall_lbl)}</text>'
            )

        parts.append('</svg>')
        return Markup("".join(parts))

    # ------------------------------------------------------------------
    # Internal helpers — wall-segment geometry. Mirrors
    # `wallSegmentsForShape` in room_geometry.esm.js so the PDF floor
    # plan and the on-screen Room Layout share one geometric model.
    # Coordinate convention: +x right, +y down (matches SVG).
    # Normals point INTO the room interior.
    # ------------------------------------------------------------------
    @staticmethod
    def _mk_seg(name, length_mm, x0, y0, x1, y1, nx, ny):
        dx_raw = x1 - x0
        dy_raw = y1 - y0
        length = math.sqrt(dx_raw * dx_raw + dy_raw * dy_raw) or 1
        return {
            "name": name,
            "length_mm": length_mm,
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "dx": dx_raw / length, "dy": dy_raw / length,
            "normalX": nx, "normalY": ny,
        }

    @classmethod
    def _wall_segments_for_shape(cls, shape, walls):
        """Mirror of room_geometry.esm.js wallSegmentsForShape.

        `walls` is a list of (name, length_mm) tuples in wall order.
        Returns None for shapes without first-class polyline support
        (caller renders the stacked fallback).
        """
        gap = _DEFAULT_GALLEY_GAP_MM
        safe = [(n or "", max(0, int(ln or 0))) for (n, ln) in (walls or [])]

        if shape == "straight" and len(safe) >= 1:
            n, ln = safe[0]
            return [cls._mk_seg(n, ln, 0, 0, ln, 0, 0, 1)]

        if shape == "l_shape" and len(safe) >= 2:
            (na, la), (nb, lb) = safe[0], safe[1]
            return [
                cls._mk_seg(na, la, 0, 0, la, 0, 0, 1),
                cls._mk_seg(nb, lb, la, 0, la, lb, -1, 0),
            ]

        if shape == "u_shape" and len(safe) >= 3:
            (na, la), (nb, lb), (nc, lc) = safe[0], safe[1], safe[2]
            return [
                cls._mk_seg(na, la, 0, 0, la, 0, 0, 1),
                cls._mk_seg(nb, lb, la, 0, la, lb, -1, 0),
                cls._mk_seg(nc, lc, la, lb, la - lc, lb, 0, -1),
            ]

        if shape == "galley" and len(safe) >= 2:
            (na, la), (nb, lb) = safe[0], safe[1]
            return [
                cls._mk_seg(na, la, 0, 0, la, 0, 0, 1),
                cls._mk_seg(nb, lb, 0, gap, lb, gap, 0, -1),
            ]

        return None

    @staticmethod
    def _dashed_gap_rect(segment, start_mm, width_mm, depth_mm, proj):
        """Emit a dashed-outline rect for an unused wall segment, with
        the mm-width label centred."""
        s = segment
        p0 = proj(s["x0"] + s["dx"] * start_mm,
                  s["y0"] + s["dy"] * start_mm)
        p1 = proj(s["x0"] + s["dx"] * (start_mm + width_mm),
                  s["y0"] + s["dy"] * (start_mm + width_mm))
        p2 = proj(s["x0"] + s["dx"] * (start_mm + width_mm)
                  + s["normalX"] * depth_mm,
                  s["y0"] + s["dy"] * (start_mm + width_mm)
                  + s["normalY"] * depth_mm)
        p3 = proj(s["x0"] + s["dx"] * start_mm
                  + s["normalX"] * depth_mm,
                  s["y0"] + s["dy"] * start_mm
                  + s["normalY"] * depth_mm)
        points_str = (
            f"{p0[0]:.1f},{p0[1]:.1f} "
            f"{p1[0]:.1f},{p1[1]:.1f} "
            f"{p2[0]:.1f},{p2[1]:.1f} "
            f"{p3[0]:.1f},{p3[1]:.1f}"
        )
        cx = (p0[0] + p1[0] + p2[0] + p3[0]) / 4
        cy = (p0[1] + p1[1] + p2[1] + p3[1]) / 4
        return (
            f'<polygon points="{points_str}" fill="none" '
            f'stroke="#776B5C" stroke-width="1" '
            f'stroke-dasharray="6 4"/>'
            f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" '
            f'style="font-family: Helvetica, sans-serif; '
            f'font-size: 8px; fill: #776B5C;">'
            f'{int(width_mm)} mm gap</text>'
        )
