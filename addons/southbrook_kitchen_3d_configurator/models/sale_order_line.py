# SPDX-License-Identifier: LGPL-3.0-only
"""Recommendation D — Sprint 1 bridge fields on sale.order.line.

Per the unification plan (see docs/southbrook_kitchen_audit_2026-07-01.md
§P0#3 and the Rec D synthesis), sale.order.line becomes the canonical
"cabinet slot" — the 3D scene node identity, its spatial placement,
and its config.session all live here. Existing `wall_id` +
`position_from_left_mm` + `is_positioned` (from southbrook_estimating)
handle wall-anchored placement; the new fields below add the free-floor
world coordinates + rotation + pin state the 3D scene needs, plus a
`sb_layout_key` stable identifier and a `sb_layout_origin` provenance
flag matching the pattern already on southbrook.kitchen.design.line.

Naming: `sb_layout_*` prefix to (a) avoid the shadow with Odoo core
`sale.order.origin`, (b) preserve unit convention (mm) consistent with
existing `position_from_left_mm` and `sb_width_mm`, and (c) make cross-
model grep parity obvious against the design.line twin fields.

`config_session_id` is intentionally NOT redefined here — it already
exists on sale.order.line via OCA `product_configurator_sale`
(`models/sale.py:34`). We reuse it verbatim.
"""

from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # ── Free-floor / world placement (islands, peninsulas, or any
    #    cabinet the user drops into open room space rather than
    #    against a wall). When `wall_id` is set (existing field from
    #    southbrook_estimating), `position_from_left_mm` is
    #    authoritative and these three coordinates are DERIVED at
    #    read time by the projection helper. When `wall_id` is null
    #    (island / free-floor), these three are authoritative. See
    #    Rec D §6 for the coordinate reconciliation rule.
    sb_layout_x_mm = fields.Float(
        string="Layout X (mm)",
        digits=(10, 2),
        help="World-space X coordinate of the cabinet's origin corner. "
             "Authoritative for free-floor cabinets (wall_id null); "
             "derived from wall+position_from_left_mm otherwise.",
    )
    sb_layout_y_mm = fields.Float(
        string="Layout Y (mm)",
        digits=(10, 2),
        help="World-space Y coordinate (depth into room).",
    )
    sb_layout_z_mm = fields.Float(
        string="Layout Z (mm)",
        digits=(10, 2),
        help="World-space Z coordinate (vertical offset from floor).",
    )
    sb_layout_rotation_deg = fields.Float(
        string="Rotation (°)",
        digits=(6, 2),
        default=0.0,
        help="Y-axis rotation in degrees (0/90/180/270 typical).",
    )
    sb_layout_pinned = fields.Boolean(
        string="Pinned",
        default=False,
        help="Set to True the first time the user manually drags or "
             "rotates this cabinet in the 3D scene. Once pinned, auto-"
             "layout leaves it alone and un-pinned neighbours pack "
             "around it.",
    )
    sb_layout_key = fields.Char(
        string="Layout Key",
        index=True,
        help="Stable identifier matching the 3D configurator's per-"
             "cabinet key. Used for non-destructive save + reconciliation "
             "with southbrook.kitchen.design.line during Sprint 1.",
    )
    sb_layout_origin = fields.Selection(
        selection=[
            ("configurator", "3D Configurator"),
            ("manual",       "Manual / Backend"),
        ],
        string="Layout Source",
        default="manual",
        help="Lines from the configurator can be replaced on re-save; "
             "manual lines are preserved across configurator saves. "
             "Mirrors the same-named field on southbrook.kitchen.design."
             "line for cross-model traceability during the Rec D "
             "reconciliation phase.",
    )

    # Reverse pointer from the Sprint-1 bridge on
    # southbrook.kitchen.design.line so the reconciliation cron can
    # walk design.line ↔ sale.order.line in either direction. Defined
    # as computed inverse to keep the write direction one-way.
    sb_design_line_ids = fields.One2many(
        "southbrook.kitchen.design.line",
        "sale_order_line_id",
        string="Bridged Design Lines",
    )

    # ── Task B3 (Materials geometry-writeback plan, Increment B) ────────
    # Per-instance cabinet dims (mm), carried over from the 3D
    # configurator's southbrook.kitchen.design.line.width_in/height_in/
    # depth_in (see kitchen_design.py's SouthbrookKitchenDesignLine.
    # _sb_dims_mm, ×25.4, rounded) — including any drag-resize or filler
    # override. 0 = no per-instance override captured on this line
    # (manual/backend line, or the design line's dims were incomplete);
    # downstream weight computation falls back to the variant's nominal
    # geometry. Named to match mrp.bom.line.sb_line_width_mm/height_mm/
    # depth_mm (sb_material_mrp, Task B1) for cross-model grep parity —
    # this module does NOT depend on sb_material_mrp, so consumers must
    # soft-guard (see _sb_apply_dims_to_bom_line below).
    sb_line_width_mm = fields.Integer(
        string="Cabinet Width Override (mm)",
        default=0,
        help="Per-instance cabinet width (mm) from the 3D configurator's "
             "design line, incl. drag-resize/filler overrides. 0 = none "
             "captured.",
    )
    sb_line_height_mm = fields.Integer(
        string="Cabinet Height Override (mm)",
        default=0,
        help="Per-instance cabinet height (mm) from the 3D configurator's "
             "design line, incl. drag-resize/filler overrides. 0 = none "
             "captured.",
    )
    sb_line_depth_mm = fields.Integer(
        string="Cabinet Depth Override (mm)",
        default=0,
        help="Per-instance cabinet depth (mm) from the 3D configurator's "
             "design line, incl. drag-resize/filler overrides. 0 = none "
             "captured.",
    )

    def _sb_apply_dims_to_bom_line(self, bom_line):
        """Task B3 — copy this SO line's per-instance dims (mm) onto a
        SPECIFIC `mrp.bom.line` recordset's sb_line_width_mm/height_mm/
        depth_mm (sb_material_mrp Task B1 fields, consumed by
        `_panel_volume_mm3`, Task B2).

        This is the narrow, direct mapping seam — it does NOT resolve
        or search for "the" bom.line to update; the caller must supply
        one it already knows is safe to write (see the caveat below).

        Soft-guards (both no-ops, never raise):
          * `sb_material_mrp` not installed -> `sb_line_width_mm` isn't
            a field on `mrp.bom.line` -> returns without writing.
          * this SO line carries no real per-instance override (any of
            the three mm fields is 0) -> returns without writing,
            mirroring the same all-or-nothing contract everywhere else
            in the geometry-writeback chain.

        CAVEAT (see docs/sdd-briefs/geo-B3-report.md "BoM-build path"
        finding): `southbrook_kitchen_3d_configurator`'s own BoM-autoseed
        path (`kitchen_design._ensure_kitchen_bom`) resolves ONE
        `mrp.bom` per `product.template`, shared by every design/order
        that uses that template/product — most visibly the filler-panel
        SKU, which is deliberately reused across many rooms with a
        DIFFERENT remainder width each time. Calling this method with a
        bom.line drawn from that shared, autoseeded BOM would silently
        make the last-quoted room's cut width win for every other
        room's filler too. This method is intentionally NOT wired into
        `_ensure_kitchen_bom` for that reason; it is exposed and tested
        as the correct, narrow mapping primitive for a future per-order/
        per-placement BoM (or any other caller that owns a bom.line
        genuinely scoped to this one SO line).
        """
        self.ensure_one()
        if "sb_line_width_mm" not in bom_line._fields:
            return
        if not (self.sb_line_width_mm and self.sb_line_height_mm
                and self.sb_line_depth_mm):
            return
        bom_line.write({
            "sb_line_width_mm":  self.sb_line_width_mm,
            "sb_line_height_mm": self.sb_line_height_mm,
            "sb_line_depth_mm":  self.sb_line_depth_mm,
        })
