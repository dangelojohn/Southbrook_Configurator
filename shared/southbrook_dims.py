# SPDX-License-Identifier: LGPL-3.0-only
"""SAMI / Southbrook Cabinetry — canonical 7-panel formulas (single source).

Peter Tuschak signed off these formulas on 2026-06-09 (G2 closed). Treat them
as final. Geometric conventions: NF14 (frameless euro construction, metric mm).

This module is intentionally Odoo-free so it can be imported by:
  - addons/southbrook_estimating/models/mrp_bom.py
        (Odoo BoM math — existing implementation at _compute_panel_dimensions;
        eventual convergence is enforced by Module 2's G1 assertion suite)
  - services/freecad_bridge/scripts/render_cabinet.py
        (FreeCAD render dimensions)
  - addons/southbrook_estimating_website/static/src/js/parametric_carcass.esm.js
        (Three.js — uses the .js sibling in this directory)
  - addons/southbrook_freecad_bridge/tests/test_bom_contents.py
        (Module-2 G1 gate — asserts create_get_bom output matches the formulas here)

Convention: a panel cut tuple is (length_mm, width_mm, thickness_mm).
"""
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Geometric constants — signed off 2026-06-09 (Peter Tuschak, G2 closed).
# ---------------------------------------------------------------------------
BOX_TH: float = 15.875        # 5/8" melamine — carcass material thickness
BACK_TH: float = 6.35         # 1/4" hardboard — back panel
RABBET: float = 6.35          # rabbet depth for back-panel capture
DOOR_TH: float = 18.0         # 3/4" slab/5-piece — door or drawer front
DOOR_REVEAL: float = 3.0      # uniform gap on all four door edges
SHELF_TOL: float = 1.5        # hand-placement clearance, subtracted from inside_width
SHELF_VENT_GAP: float = 12.7  # 1/2" ventilation gap subtracted from depth at the back
TOEKICK_H: float = 101.6      # 4" — toe-kick height (integrated into sides, see toe_kick())

TOEKICK_FAMILIES = frozenset({"base", "sink", "tall", "vanity"})

PanelCut = Tuple[float, float, float]


# ---------------------------------------------------------------------------
# 7 canonical panel formulas
# ---------------------------------------------------------------------------
def side(height_mm: float, depth_mm: float) -> PanelCut:
    """Side panel (L or R) — full-height frameless side.

    The toe-kick (for families that have one) is integrated as a routed notch
    in the front-bottom corner of this panel — there is NO separate toe-kick
    cut. See toe_kick() for the metadata descriptor.
    """
    return (height_mm, depth_mm, BOX_TH)


def top(width_mm: float, depth_mm: float) -> PanelCut:
    """Top panel — captures between the sides (frameless euro)."""
    inside_width = width_mm - 2 * BOX_TH
    return (inside_width, depth_mm, BOX_TH)


def bottom(width_mm: float, depth_mm: float) -> PanelCut:
    """Bottom panel — captures between the sides (frameless euro)."""
    inside_width = width_mm - 2 * BOX_TH
    return (inside_width, depth_mm, BOX_TH)


def back(width_mm: float, height_mm: float) -> PanelCut:
    """Back panel — captures into rabbet on sides/top/bottom."""
    inside_width = width_mm - 2 * BOX_TH
    length = inside_width + 2 * RABBET
    width = (height_mm - 2 * BOX_TH) + 2 * RABBET
    return (length, width, BACK_TH)


def adjustable_shelf(width_mm: float, depth_mm: float) -> PanelCut:
    """One adjustable shelf — quantity comes from shelf_count(height)."""
    inside_width = width_mm - 2 * BOX_TH
    length = inside_width - SHELF_TOL
    width = depth_mm - BACK_TH - RABBET - SHELF_VENT_GAP
    return (length, width, BOX_TH)


def shelf_count(height_mm: float) -> int:
    """Shelf quantity from cabinet height — NF14 heuristic."""
    if height_mm <= 600:
        return 1
    if height_mm <= 900:
        return 2
    return 3


def door(width_mm: float, height_mm: float, door_count: int) -> Optional[PanelCut]:
    """Door (or drawer-front) panel sized from door_count and uniform reveal.

    Returns None if door_count is 0 (e.g. open shelving).
    """
    if door_count == 1:
        return (height_mm - 2 * DOOR_REVEAL, width_mm - 2 * DOOR_REVEAL, DOOR_TH)
    if door_count == 2:
        return (height_mm - 2 * DOOR_REVEAL, (width_mm - 3 * DOOR_REVEAL) / 2, DOOR_TH)
    return None


def toe_kick(family: str, width_mm: float) -> Optional[Dict[str, Any]]:
    """Toe-kick descriptor.

    Phase 1/2 construction: the toe-kick is INTEGRATED into the side panels
    via a notch routed into the front-bottom corner. There is NO separate
    toe-kick panel cut. This function returns metadata describing the
    integration (height + applicability), NOT a panel cut tuple, so callers
    do not mistakenly emit a separate piece on the cut list.

    Returns None for families without a toe-kick (e.g. wall).
    """
    if family not in TOEKICK_FAMILIES:
        return None
    return {
        "integrated_into_sides": True,
        "height_mm": TOEKICK_H,
        "thickness_mm": BOX_TH,
    }


# ---------------------------------------------------------------------------
# Convenience: full panel cut list for a parametric carcass
# ---------------------------------------------------------------------------
def panel_cut_list(
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    family: str = "base",
    door_count: int = 1,
) -> Dict[str, Any]:
    """Complete 7-panel descriptor for a parametric carcass.

    Mirrors southbrook_estimating/models/mrp_bom.py::_compute_panel_dimensions
    so the BoM-contents assertion suite (Module 2 / G1) can compare the two
    for byte-identical parity. Any drift between the two is a manufacturing-
    safety regression by construction.
    """
    shelves = shelf_count(height_mm)
    return {
        "side_L": side(height_mm, depth_mm),
        "side_R": side(height_mm, depth_mm),
        "top": top(width_mm, depth_mm),
        "bottom": bottom(width_mm, depth_mm),
        "back": back(width_mm, height_mm),
        "adjustable_shelf": adjustable_shelf(width_mm, depth_mm) if shelves > 0 else None,
        "shelf_count": shelves,
        "door": door(width_mm, height_mm, door_count),
        "door_count": door_count,
        "toe_kick": toe_kick(family, width_mm),
    }
