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

    # ── Geometric corner detection (2026-07-12, corner-cell footprint) ──
    # The "vanishing cabinet" bug: detect_corners used to activate a corner
    # the instant BOTH walls carried ANY cabinet of a layer — so adding the
    # very FIRST cabinet to a second wall could immediately fire a corner
    # resolution and silently consume it, even though the two runs were
    # nowhere near each other. Passing `placements` makes detection require
    # each wall's cabinet to GEOMETRICALLY reach the corner's footprint
    # cell, not merely exist on that wall.
    def test_corner_detected_only_when_footprints_reach_corner_cell(self):
        back = {"id": "B", "width_mm": 600, "depth_mm": 600,
                "wall": "back", "cabinet_type": "base"}
        left = {"id": "L", "width_mm": 600, "depth_mm": 600,
                "wall": "left", "cabinet_type": "base"}
        # Both cabinets actually occupy the back-left cell (914mm square at
        # the origin) → corner detected.
        placements = [
            {"id": "B", "x": 300, "y": 0, "z": 0, "rotation_deg": 0},
            {"id": "L", "x": 0, "y": 0, "z": 300, "rotation_deg": 90},
        ]
        got = E.detect_corners([back, left], ROOM, placements=placements)
        self.assertEqual(self._names(got), [("back-left", "base")])

        # Same back cabinet, but the left cabinet is placed FAR down the
        # left wall (near the front of the room) — its footprint never
        # reaches the corner cell, so no corner should be detected even
        # though the left wall nominally "has a cabinet".
        left_far = {"id": "L2", "width_mm": 600, "depth_mm": 600,
                    "wall": "left", "cabinet_type": "base"}
        placements_far = [
            {"id": "B", "x": 300, "y": 0, "z": 0, "rotation_deg": 0},
            {"id": "L2", "x": 0, "y": 0, "z": 2700, "rotation_deg": 90},
        ]
        got_far = E.detect_corners(
            [back, left_far], ROOM, placements=placements_far)
        self.assertEqual(got_far, [])

    def test_back_only_kitchen_detects_no_corner(self):
        """Parity guard: a straight back-only kitchen never detects a
        corner — geometric detection must not regress the common case."""
        cabs = [
            {"id": 1, "width_mm": 600, "height_mm": 762, "depth_mm": 600,
             "family": "base", "zone": "base_run", "wall": "back",
             "cabinet_type": "base"},
            {"id": 2, "width_mm": 900, "height_mm": 762, "depth_mm": 600,
             "family": "base", "zone": "base_run", "wall": "back",
             "cabinet_type": "base"},
            {"id": 3, "width_mm": 600, "height_mm": 720, "depth_mm": 300,
             "family": "wall", "zone": "wall", "wall": "back",
             "cabinet_type": "wall"},
        ]
        placements = E.layout(copy.deepcopy(cabs), ROOM, ZL, WC, WY)
        self.assertEqual(E.detect_corners(cabs, ROOM, placements=placements), [])

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

    def test_resolve_generates_manufacturable_U(self):
        # A manually-placed U: left + back + right. BOTH back corners must be
        # reserved (back-left low/low, back-right where the back run meets the
        # right run at its HIGH end). The load-bearing property is that NO two
        # cabinets overlap once the corners are resolved.
        #
        # Geometric detection (2026-07-12) requires the back run to actually
        # REACH the back-right corner cell to be detected there — a real U,
        # not just "some cabinet exists on each wall". 6 back cabinets (not
        # 5) span far enough into a slightly wider room (4300mm, not 4000mm)
        # to reach the cell while the single-cabinet corner-side trim still
        # leaves no residual overlap.
        room = {"width_mm": 4300, "depth_mm": 3000, "height_mm": 2400}
        def mk(cid, wall, seq, ct="base"):
            return {"id": cid, "width_mm": 600,
                    "height_mm": 876 if ct != "wall" else 720,
                    "depth_mm": 600 if ct != "wall" else 320,
                    "family": ct if ct == "wall" else "base",
                    "cabinet_type": ct,
                    "zone": "wall" if ct == "wall" else "base_run",
                    "wall": wall, "run_seq": seq}
        cabs = ([mk(("L", s), "left", s) for s in range(3)]
                + [mk(("B", s), "back", s) for s in range(6)]
                + [mk(("R", s), "right", s) for s in range(3)])
        r = E.resolve_and_layout(cabs, room, auto_assign=False)
        corners = sorted(c["corner"] for c in r["cabinets"]
                         if c.get("corner_cabinet"))
        self.assertEqual(corners, ["back-left", "back-right"])
        handed = {c["corner"]: c["handed"] for c in r["cabinets"]
                  if c.get("corner_cabinet")}
        self.assertEqual(handed, {"back-left": "L", "back-right": "R"})
        # 12 in − 4 replaced (2 per corner) + 2 corners = 10
        self.assertEqual(len(r["cabinets"]), 10)
        pl = {p["id"]: p for p in r["placements"]}
        # THE invariant: no cabinet overlaps another (incl. both corner cells).
        fps = [(c["id"], E.footprint_mm(c, pl[c["id"]])) for c in r["cabinets"]]
        for i in range(len(fps)):
            for j in range(i + 1, len(fps)):
                self.assertFalse(
                    E.footprints_overlap(fps[i][1], fps[j][1]),
                    "overlap: %s vs %s" % (fps[i][0], fps[j][0]))
        # every cabinet stays inside the room
        for c in r["cabinets"]:
            self.assertTrue(E.within_room(c, pl[c["id"]], room),
                            "outside room: %s" % (c["id"],))
        # back-right corner sits against the right wall near (W, 0)
        br = [c for c in r["cabinets"]
              if c.get("corner") == "back-right"][0]
        self.assertEqual(br["wall"], "right")
        self.assertGreater(pl[br["id"]]["x"], 3000)
        self.assertLess(pl[br["id"]]["z"], 1000)

    @staticmethod
    def _mkw(cid, wall, seq, ct="base"):
        return {"id": cid, "width_mm": 600,
                "height_mm": 876 if ct != "wall" else 720,
                "depth_mm": 600 if ct != "wall" else 320,
                "family": ct if ct == "wall" else "base", "cabinet_type": ct,
                "zone": "wall" if ct == "wall" else "base_run",
                "wall": wall, "run_seq": seq}

    def _assert_clean(self, r, room):
        """No two footprints overlap and every cabinet is within the room —
        the load-bearing manufacturability invariant."""
        pl = {p["id"]: p for p in r["placements"]}
        fps = [(c["id"], E.footprint_mm(c, pl[c["id"]])) for c in r["cabinets"]]
        for i in range(len(fps)):
            for j in range(i + 1, len(fps)):
                self.assertFalse(
                    E.footprints_overlap(fps[i][1], fps[j][1]),
                    "overlap: %s vs %s" % (fps[i][0], fps[j][0]))
        for c in r["cabinets"]:
            self.assertTrue(E.within_room(c, pl[c["id"]], room),
                            "outside room: %s" % (c["id"],))
        return pl

    def test_resolve_front_left_corner(self):
        # front-left has a low-end host (front run's origin), same model as
        # back-right — corner joins the front run at run_seq -1.
        #
        # Geometric detection (2026-07-12) requires the left run to actually
        # REACH the front-left corner cell (near the front wall) to be
        # detected there — 4 left cabinets (not 3) span far enough.
        cabs = ([self._mkw(("F", s), "front", s) for s in range(4)]
                + [self._mkw(("L", s), "left", s) for s in range(4)])
        r = E.resolve_and_layout(cabs, ROOM, auto_assign=False)
        fl = [c for c in r["cabinets"] if c.get("corner") == "front-left"]
        self.assertEqual(len(fl), 1)
        self.assertEqual(fl[0]["wall"], "front")
        self.assertEqual(fl[0]["run_seq"], -1)
        pl = self._assert_clean(r, ROOM)
        # sits in the front-left cell: low x, high z (near the front wall)
        self.assertLess(pl[fl[0]["id"]]["x"], 1000)
        self.assertGreater(pl[fl[0]["id"]]["z"], 2000)

    def test_resolve_front_right_standalone_and_cap(self):
        # front-right is "both-high" — neither wall's low end is at it, so the
        # corner is placed STANDALONE (explicit pose) and the two runs are
        # capped. Long runs (front 6, right 5) force the cap pass to fire.
        cabs = ([self._mkw(("F", s), "front", s) for s in range(6)]
                + [self._mkw(("R", s), "right", s) for s in range(5)])
        r = E.resolve_and_layout(cabs, ROOM, auto_assign=False)
        fr = [c for c in r["cabinets"] if c.get("corner") == "front-right"]
        self.assertEqual(len(fr), 1)
        self.assertIsNotNone(fr[0].get("__pose"))         # standalone
        self.assertNotIn("run_seq", fr[0])                 # not joined to a run
        self.assertGreaterEqual(len(fr[0]["replaced_ids"]), 1)   # cap fired
        # the capped cabinets are truly gone from the output
        out_ids = {c["id"] for c in r["cabinets"]}
        for cid in fr[0]["replaced_ids"]:
            self.assertNotIn(cid, out_ids)
        pl = self._assert_clean(r, ROOM)
        self.assertGreater(pl[fr[0]["id"]]["x"], 3000)     # near (W, D)
        self.assertGreater(pl[fr[0]["id"]]["z"], 2000)

    def test_resolve_full_g_shape_four_corners(self):
        # All four walls occupied → all four corners reserved, nothing
        # overlaps, each corner in its own quadrant.
        #
        # Geometric detection (2026-07-12) requires each run to actually
        # REACH both of its corner cells — a real G-shape, not just "some
        # cabinet on each wall". back/front need 9 cabinets (long walls,
        # 6200mm) and left/right need 7 (5000mm) to reach into the FAR
        # corner cell from each run's low end while the single-cabinet
        # corner-side trim still leaves no residual overlap.
        big = {"width_mm": 6200, "depth_mm": 5000, "height_mm": 2400}
        wall_counts = {"back": 9, "front": 9, "left": 7, "right": 7}
        cabs = []
        for wall, n in wall_counts.items():
            cabs += [self._mkw((wall, s), wall, s) for s in range(n)]
        r = E.resolve_and_layout(cabs, big, auto_assign=False)
        corners = sorted(c["corner"] for c in r["cabinets"]
                         if c.get("corner_cabinet"))
        self.assertEqual(
            corners, ["back-left", "back-right", "front-left", "front-right"])
        pl = self._assert_clean(r, big)
        q = {c["corner"]: pl[c["id"]] for c in r["cabinets"]
             if c.get("corner_cabinet")}
        self.assertTrue(q["back-left"]["x"] < 3000 and q["back-left"]["z"] < 2500)
        self.assertTrue(q["back-right"]["x"] > 3000 and q["back-right"]["z"] < 2500)
        self.assertTrue(q["front-left"]["x"] < 3000 and q["front-left"]["z"] > 2500)
        self.assertTrue(q["front-right"]["x"] > 3000 and q["front-right"]["z"] > 2500)
