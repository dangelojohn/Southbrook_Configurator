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
