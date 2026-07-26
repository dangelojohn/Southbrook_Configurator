# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models

# I-3 (final review, 2026-07-26) — CORRECTED CLAIM. These role codes must
# match the panel-dict keys `_compute_panel_dimensions` returns
# (sb_material_mrp/models/mrp_bom.py: side_L/side_R/top/bottom/back/shelf/
# door) — the exact-volume code (`_sb_line_exact_volume_mm3`) looks panels
# up by these exact keys, so do NOT rename them.
#
# The previous comment here claimed this vocabulary "MUST match
# sb.cutlist.PANEL_NAMES" (southbrook_kitchen_mrp/models/sb_cutlist.py).
# That is FALSE as verified: the real `PANEL_NAMES` uses
# `adjustable_shelf`, not `shelf` (the door label also differs — "Door /
# Drawer Face" vs "Door" here — though the door CODE does match). No
# functional impact today (these roles only drive `_compute_panel_
# dimensions` keys, which this vocabulary already matches correctly), but
# a future `sb.cutlist` convergence keying on `code == panel_name` would
# silently fail to map shelves. Converging with `sb.cutlist.PANEL_NAMES`
# later requires an explicit `shelf` <-> `adjustable_shelf` (and
# door-label) mapping — do not assume identity.
PANEL_ROLE_KEYS = ("side_L", "side_R", "top", "bottom", "back", "shelf", "door")


class SbPanelRole(models.Model):
    _name = "sb.panel.role"
    _description = "Cabinet Panel Role"
    _order = "sequence, code"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)

    _unique_code = models.Constraint("unique(code)", "Panel role code must be unique.")
