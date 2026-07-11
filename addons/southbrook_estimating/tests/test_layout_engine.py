# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the pure kitchen layout engine.

The engine has no ORM dependency, so these are plain-logic assertions. The
load-bearing one is `test_golden_backwall_parity`: it proves the engine
reproduces the legacy single-run math byte-for-byte, so routing the Preview
and design-line seeding through the engine (P0.2) cannot regress existing
straight kitchens.
"""
import copy

from odoo.tests.common import TransactionCase
from odoo.addons.southbrook_estimating.models import kitchen_layout_engine as E

ZL = E._DEFAULT_ZONE_LAYOUT
WC = E._DEFAULT_WORKTOP_CURSOR
WY = E._DEFAULT_WORKTOP_Y
ROOM = {"width_mm": 4000, "depth_mm": 3000, "height_mm": 2400}


def _legacy_backwall(cabinets):
    """Faithful copy of the CURRENT single-run math in
    sale_order.get_kitchen_3d_payload / _southbrook_seed_design_lines."""
    cursors = {"ground": 0, "wall": 0, "island": 0, "other": 0}
    out = []
    for cab in cabinets:
        w = cab["width_mm"]
        if cab.get("family") == "worktop":
            cursor_name, y_floor, z_offset = WC, WY, 0
        else:
            zone = cab.get("zone") or "base_run"
            cursor_name, y_floor, z_offset = ZL.get(zone, ("ground", 0, 0))
        x_offset = cursors[cursor_name] + w / 2.0
        out.append({"id": cab["id"], "x": x_offset, "y": y_floor, "z": z_offset})
        cursors[cursor_name] += w
    return out


class TestKitchenLayoutEngine(TransactionCase):

    def test_golden_backwall_parity(self):
        cabs = [
            {"id": 1, "width_mm": 600, "height_mm": 762, "depth_mm": 600, "family": "base", "zone": "base_run", "wall": "back"},
            {"id": 2, "width_mm": 900, "height_mm": 762, "depth_mm": 600, "family": "base", "zone": "base_run", "wall": "back"},
            {"id": 3, "width_mm": 600, "height_mm": 720, "depth_mm": 300, "family": "wall", "zone": "wall", "wall": "back"},
            {"id": 4, "width_mm": 600, "height_mm": 2100, "depth_mm": 600, "family": "tall", "zone": "tall", "wall": "back"},
            {"id": 5, "width_mm": 1200, "height_mm": 25, "depth_mm": 650, "family": "worktop", "zone": "base_run", "wall": "back"},
            {"id": 6, "width_mm": 1000, "height_mm": 900, "depth_mm": 600, "family": "base", "zone": "island", "wall": "back"},
        ]
        legacy = _legacy_backwall(cabs)
        got = E.layout(copy.deepcopy(cabs), ROOM, ZL, WC, WY)
        self.assertEqual(len(legacy), len(got))
        for lg, g in zip(legacy, got):
            self.assertEqual(lg["id"], g["id"])
            self.assertAlmostEqual(lg["x"], g["x"], places=6)
            self.assertAlmostEqual(lg["y"], g["y"], places=6)
            self.assertAlmostEqual(lg["z"], g["z"], places=6)
            self.assertAlmostEqual(g["rotation_deg"], 0, places=6)

    def test_side_and_front_walls(self):
        W, D = ROOM["width_mm"], ROOM["depth_mm"]
        cabs = [
            {"id": "L1", "width_mm": 600, "family": "base", "zone": "base_run", "wall": "left", "run_seq": 0},
            {"id": "L2", "width_mm": 900, "family": "base", "zone": "base_run", "wall": "left", "run_seq": 1},
            {"id": "R1", "width_mm": 600, "family": "base", "zone": "base_run", "wall": "right", "run_seq": 0},
            {"id": "F1", "width_mm": 600, "family": "base", "zone": "base_run", "wall": "front", "run_seq": 0},
        ]
        got = {p["id"]: p for p in E.layout(cabs, ROOM, ZL, WC, WY)}
        self.assertAlmostEqual(got["L1"]["x"], 0)
        self.assertAlmostEqual(got["L1"]["z"], 300)
        self.assertAlmostEqual(got["L1"]["rotation_deg"], 90)
        self.assertAlmostEqual(got["L2"]["z"], 600 + 450)
        self.assertAlmostEqual(got["R1"]["x"], W)
        self.assertAlmostEqual(got["R1"]["rotation_deg"], 270)
        self.assertAlmostEqual(got["F1"]["z"], D)
        self.assertAlmostEqual(got["F1"]["rotation_deg"], 180)

    def test_default_wall_is_back(self):
        cabs = [{"id": 1, "width_mm": 600, "family": "base", "zone": "base_run"}]
        got = E.layout(cabs, ROOM, ZL, WC, WY)
        self.assertAlmostEqual(got[0]["rotation_deg"], 0)
        self.assertAlmostEqual(got[0]["z"], 0)

    def test_deterministic_and_no_mutation(self):
        cabs = [
            {"id": 1, "width_mm": 600, "family": "base", "zone": "base_run", "wall": "left", "run_seq": 5},
            {"id": 2, "width_mm": 600, "family": "base", "zone": "base_run", "wall": "left", "run_seq": 1},
        ]
        snapshot = copy.deepcopy(cabs)
        a = E.layout(cabs, ROOM, ZL, WC, WY)
        b = E.layout(cabs, ROOM, ZL, WC, WY)
        self.assertEqual(cabs, snapshot)
        self.assertEqual(a, b)
        by = {p["id"]: p for p in a}
        self.assertLess(by[2]["z"], by[1]["z"])
        self.assertEqual([p["id"] for p in a], [1, 2])

    # ── Corner detection (P2) ───────────────────────────────────────────
    def _cab(self, wall, ct="base"):
        return {"id": wall + ct, "width_mm": 600,
                "family": ct if ct == "wall" else "base",
                "cabinet_type": ct, "wall": wall}

    @staticmethod
    def _names(corners):
        return sorted((c["corner"], c["layer"]) for c in corners)

    def test_no_corner_for_single_wall(self):
        self.assertEqual(
            E.detect_corners([self._cab("back"), self._cab("back")], ROOM), [])
        self.assertEqual(
            E.detect_corners([self._cab("right"), self._cab("right")], ROOM), [])

    def test_l_shape_corner(self):
        got = E.detect_corners([self._cab("back"), self._cab("left")], ROOM)
        self.assertEqual(self._names(got), [("back-left", "base")])

    def test_base_and_wall_corners_independent(self):
        got = E.detect_corners([
            self._cab("back"), self._cab("left"),
            self._cab("back", "wall"), self._cab("left", "wall"),
        ], ROOM)
        self.assertEqual(self._names(got),
                         [("back-left", "base"), ("back-left", "wall")])

    def test_u_shape_two_corners(self):
        got = E.detect_corners(
            [self._cab("left"), self._cab("back"), self._cab("right")], ROOM)
        self.assertEqual(self._names(got),
                         [("back-left", "base"), ("back-right", "base")])
        br = [c for c in got if c["corner"] == "back-right"][0]
        self.assertEqual(br["position_mm"], {"x": 4000.0, "z": 0.0})

    # ── Auto-distribution + corner resolution (P1) ──────────────────────
    def test_auto_assign_wraps_to_side_wall(self):
        # 10x 600mm on a 4000-wide back wall → 6 fit, 4 wrap to left.
        cabs = [{"id": i, "width_mm": 600, "family": "base",
                 "cabinet_type": "base"} for i in range(10)]
        out = E.auto_assign_walls(cabs, ROOM)
        walls = {}
        for c in out:
            walls.setdefault(c["wall"], 0)
            walls[c["wall"]] += 1
        self.assertEqual(walls.get("back"), 6)
        self.assertEqual(walls.get("left"), 4)
        # inputs untouched (no wall key added to originals)
        self.assertNotIn("wall", cabs[0])

    def test_resolve_generates_manufacturable_L(self):
        cabs = [{"id": i, "width_mm": 600, "height_mm": 876, "depth_mm": 600,
                 "family": "base", "cabinet_type": "base"}
                for i in range(1, 11)]
        r = E.resolve_and_layout(cabs, ROOM)
        # one back-left corner cabinet inserted, replacing 2 standards
        self.assertEqual([n["id"] for n in r["inserted"]],
                         ["corner-back-left-base"])
        self.assertEqual(len(r["removed_ids"]), 2)
        self.assertEqual(len(r["cabinets"]), 9)   # 10 - 2 + 1
        pl = {p["id"]: p for p in r["placements"]}
        cc = pl["corner-back-left-base"]
        self.assertAlmostEqual(cc["z"], 0)
        self.assertAlmostEqual(cc["rotation_deg"], 0)
        # nothing overlaps the corner cell; runs stay within wall lengths
        back = [pl[c["id"]] for c in r["cabinets"]
                if c.get("wall") == "back" and not c.get("corner_cabinet")]
        left = [pl[c["id"]] for c in r["cabinets"] if c.get("wall") == "left"]
        self.assertGreaterEqual(min(p["x"] - 300 for p in back), 914 - 1)
        self.assertGreaterEqual(min(p["z"] - 300 for p in left), 914 - 1)
        self.assertTrue(all(abs(p["rotation_deg"] - 90) < 1 for p in left))
        self.assertLessEqual(max(p["x"] + 300 for p in back + [cc]), 4000)
        self.assertLessEqual(max(p["z"] + 300 for p in left), 3000)
