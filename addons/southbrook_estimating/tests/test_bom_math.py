# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for custom routine #1 — `_compute_panel_dimensions`.

Per NF14: tests use **re-derivation assertions** — every expected value
is computed inline from the named constants so the tests tolerate
constant updates without expected-value changes. When the canonical #8
workbook lands and `BOX_TH` flips from 15.875 to (say) 18.0, these
tests pass without modification; only the formula proof needs review.

Cabinet shapes exercised:
  1. base_1dr  — 12in x 30in x 24in (narrow base, Rule 3 = 1-door)
  2. base_2dr  — 33in x 30in x 24in (wide base, Rule 3 = 2-door)
  3. tall_pantry — 24in x 84in x 24in (height variation, 3 shelves)
  4. wall_2dr — 30in x 30in x 12in (depth variation)

Plus targeted assertions:
  - Edge-banding formula across all 4 finished_sides values
  - Drawer-bank hardware count divergence (Phase-1 simplification)
  - Shelf-count height-band heuristic boundaries
"""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase

# Re-import the same constants so tests assert against the SAME source
# of truth as the production code. Update one, test re-derivation flows.
from odoo.addons.southbrook_estimating.models.mrp_bom import (
    BOX_TH, BACK_TH, RABBET, DOOR_TH, DOOR_REVEAL,
    SHELF_TOL, SHELF_VENT_GAP,
)


@tagged("post_install", "-at_install", "southbrook", "bom_math")
class TestComputePanelDimensions(SouthbrookTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.MrpBom = cls.env["mrp.bom"]

    # ------------------------------------------------------------------
    # Shape 1 — small base 1-door: 12in (304mm) x 30in (762mm) x 24in (609mm)
    # ------------------------------------------------------------------
    def test_01_base_1dr_panel_dimensions(self):
        W, H, D = 304, 762, 609
        result = self.MrpBom._compute_panel_dimensions(
            width_mm=W, height_mm=H, depth_mm=D,
            family="base", door_count=1, finished_sides="none",
        )
        inside_width = W - 2 * BOX_TH

        # Sides: length = height, width = depth, thickness = box.
        self.assertEqual(result["side_L"], (H, D, BOX_TH))
        self.assertEqual(result["side_R"], (H, D, BOX_TH))

        # Top + bottom: between sides; length = inside_width, width = depth.
        self.assertEqual(result["top"], (inside_width, D, BOX_TH))
        self.assertEqual(result["bottom"], (inside_width, D, BOX_TH))

        # Back: rabbeted; length = inside_width + 2*RABBET, width = (H - 2*BOX_TH) + 2*RABBET.
        self.assertEqual(
            result["back"],
            (inside_width + 2 * RABBET, (H - 2 * BOX_TH) + 2 * RABBET, BACK_TH),
        )

        # Shelf: 762mm height → 2 shelves per NF14 heuristic.
        self.assertEqual(result["shelf_count"], 2)
        self.assertEqual(
            result["shelf"],
            (inside_width - SHELF_TOL, D - BACK_TH - RABBET - SHELF_VENT_GAP, BOX_TH),
        )

        # 1-door: door spans full width minus 2 reveals.
        self.assertEqual(
            result["door"],
            (H - 2 * DOOR_REVEAL, W - 2 * DOOR_REVEAL, DOOR_TH),
        )
        self.assertEqual(result["door_count"], 1)
        self.assertEqual(result["hinge_pair_count"], 1)
        self.assertEqual(result["handle_count"], 1)
        self.assertEqual(result["drawer_count"], 0)

    # ------------------------------------------------------------------
    # Shape 2 — wide base 2-door: 33in (838mm) x 30in (762mm) x 24in (609mm)
    # ------------------------------------------------------------------
    def test_02_base_2dr_panel_dimensions(self):
        W, H, D = 838, 762, 609
        result = self.MrpBom._compute_panel_dimensions(
            width_mm=W, height_mm=H, depth_mm=D,
            family="base", door_count=2, finished_sides="none",
        )
        inside_width = W - 2 * BOX_TH

        # 2-door: each door = (W - 3*REVEAL) / 2 wide, full height minus 2 reveals.
        expected_door = (
            H - 2 * DOOR_REVEAL,
            (W - 3 * DOOR_REVEAL) / 2,
            DOOR_TH,
        )
        self.assertEqual(result["door"], expected_door)
        self.assertEqual(result["door_count"], 2)
        self.assertEqual(result["hinge_pair_count"], 2)
        self.assertEqual(result["handle_count"], 2)

        # Sides, top, bottom unchanged in shape — re-derivation.
        self.assertEqual(result["side_L"], (H, D, BOX_TH))
        self.assertEqual(result["top"], (inside_width, D, BOX_TH))

    # ------------------------------------------------------------------
    # Shape 3 — tall pantry: 24in (609mm) x 84in (2134mm) x 24in (609mm)
    #          exercises 3-shelf branch of the NF14 heuristic
    # ------------------------------------------------------------------
    def test_03_tall_pantry_three_shelves(self):
        W, H, D = 609, 2134, 609
        result = self.MrpBom._compute_panel_dimensions(
            width_mm=W, height_mm=H, depth_mm=D,
            family="tall", door_count=1,
        )
        # Per NF14: height > 900 → 3 shelves.
        self.assertEqual(result["shelf_count"], 3)
        # And the side panels scale to the tall height.
        self.assertEqual(result["side_L"][0], H)
        # Back panel height grows with cabinet height too.
        self.assertEqual(result["back"][1], (H - 2 * BOX_TH) + 2 * RABBET)

    # ------------------------------------------------------------------
    # Shape 4 — wall 2-door (shallow): 30in (762mm) x 30in (762mm) x 12in (304mm)
    #          exercises depth variation (wall units are shallower)
    # ------------------------------------------------------------------
    def test_04_wall_2dr_shallow_depth(self):
        W, H, D = 762, 762, 304
        result = self.MrpBom._compute_panel_dimensions(
            width_mm=W, height_mm=H, depth_mm=D,
            family="wall", door_count=2,
        )
        # Sides are shallower (depth is the second tuple position).
        self.assertEqual(result["side_L"][1], D)
        # Shelf depth scales: depth − back inset − vent gap.
        self.assertEqual(
            result["shelf"][1],
            D - BACK_TH - RABBET - SHELF_VENT_GAP,
        )
        # 2-door geometry holds.
        self.assertEqual(result["door"][1], (W - 3 * DOOR_REVEAL) / 2)

    # ------------------------------------------------------------------
    # Edge-banding across the 4 finished_sides values — re-derivation.
    # ------------------------------------------------------------------
    def test_05_edge_banding_none(self):
        W, H, D = 762, 762, 609
        result = self.MrpBom._compute_panel_dimensions(
            width_mm=W, height_mm=H, depth_mm=D,
            family="base", door_count=2, finished_sides="none",
        )
        inside_width = W - 2 * BOX_TH
        # No side banding; just top + bottom front edges.
        expected = int(2 * inside_width)
        self.assertEqual(result["edge_banding_length_mm"], expected)

    def test_06_edge_banding_one_side(self):
        W, H, D = 762, 762, 609
        result = self.MrpBom._compute_panel_dimensions(
            width_mm=W, height_mm=H, depth_mm=D,
            family="base", door_count=2, finished_sides="left",
        )
        side_perim = 2 * (H + D)
        inside_width = W - 2 * BOX_TH
        expected = int(side_perim + 2 * inside_width)
        self.assertEqual(result["edge_banding_length_mm"], expected)

    def test_07_edge_banding_both_sides(self):
        W, H, D = 762, 762, 609
        result = self.MrpBom._compute_panel_dimensions(
            width_mm=W, height_mm=H, depth_mm=D,
            family="base", door_count=2, finished_sides="both",
        )
        side_perim = 2 * (H + D)
        inside_width = W - 2 * BOX_TH
        expected = int(2 * side_perim + 2 * inside_width)
        self.assertEqual(result["edge_banding_length_mm"], expected)

    # ------------------------------------------------------------------
    # Drawer bank — Phase-1 simplification noted in NF14
    # ------------------------------------------------------------------
    def test_08_drawer_bank_hardware_diverges_from_doors(self):
        W, H, D = 457, 762, 609
        result = self.MrpBom._compute_panel_dimensions(
            width_mm=W, height_mm=H, depth_mm=D,
            family="drawer", door_count=2, drawer_count=0,
        )
        # Drawer family: hinge_pair_count is 0; drawer-front count is
        # repurposed from door_count per NF14 Phase-1 simplification.
        self.assertEqual(result["hinge_pair_count"], 0)
        self.assertEqual(result["drawer_count"], 2)
        self.assertEqual(result["handle_count"], 2)
        self.assertEqual(result["drawer_slide_pair_count"], 2)

    # ------------------------------------------------------------------
    # Shelf-count height heuristic boundaries (per NF14)
    # ------------------------------------------------------------------
    def test_09_shelf_count_boundaries(self):
        # h <= 600 → 1 shelf
        r = self.MrpBom._compute_panel_dimensions(
            width_mm=600, height_mm=600, depth_mm=600,
            family="wall", door_count=1,
        )
        self.assertEqual(r["shelf_count"], 1)

        # 600 < h <= 900 → 2 shelves
        r = self.MrpBom._compute_panel_dimensions(
            width_mm=600, height_mm=900, depth_mm=600,
            family="wall", door_count=1,
        )
        self.assertEqual(r["shelf_count"], 2)

        # h > 900 → 3 shelves
        r = self.MrpBom._compute_panel_dimensions(
            width_mm=600, height_mm=901, depth_mm=600,
            family="tall", door_count=1,
        )
        self.assertEqual(r["shelf_count"], 3)

    # ------------------------------------------------------------------
    # No-door case — accessory + worktop have door_count=0
    # ------------------------------------------------------------------
    def test_10_zero_door_count_emits_no_door(self):
        result = self.MrpBom._compute_panel_dimensions(
            width_mm=600, height_mm=600, depth_mm=600,
            family="accessory", door_count=0,
        )
        self.assertIsNone(result["door"])
        self.assertEqual(result["door_count"], 0)
        self.assertEqual(result["hinge_pair_count"], 0)
        self.assertEqual(result["handle_count"], 0)
