# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room.wall.conflict_count — 2026-07-03 QA follow-up.

QA found: a Sink constraint at distance_from_left_mm=2800 / width_mm=600
on a wall, after the wall is resized down to ~2590mm, leaves the
constraint hanging past the wall end (2800 + 600 = 3400 > 2590) yet
`has_conflicts` stayed False. Root cause was NOT the overrun math itself
(southbrook_estimating_website/tests/test_room_geometry.py already
covers `has_constraint_out_of_bounds` for a static overrun) but the
absence of a per-wall conflict TALLY the Room Layout metrics table could
render — the client only ever had the single boolean, so "does this wall
have exactly one problem or five" was indistinguishable.

This file exercises the new `conflict_count` field end to end, including
the resize-toggle behaviour (grow clears an overrun, shrink re-triggers
it) that the QA report specifically called out.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_room_wall")
class TestRoomWallConflictCount(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Conflict Count Cust"})
        cls.order = cls.env["sale.order"].create({"partner_id": cls.partner.id})
        cls.room = cls.env["southbrook.room"].create({
            "name": "K", "order_id": cls.order.id,
            "layout_shape": "straight",
            "wall_ids": [(0, 0, {"name": "A", "length_mm": 3000})],
        })
        cls.wall = cls.room.wall_ids[0]

    def test_overrun_constraint_flags_conflict_and_counts_one(self):
        # Sink 600mm wide @ 2800mm on a 3000mm wall → 2800 + 600 = 3400,
        # 400mm past the wall end.
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall.id, "constraint_type": "sink",
            "distance_from_left_mm": 2800, "width_mm": 600,
        })
        self.wall.invalidate_recordset()
        self.assertTrue(self.wall.has_conflicts)
        self.assertTrue(self.wall.has_constraint_out_of_bounds)
        self.assertGreaterEqual(self.wall.conflict_count, 1)
        self.assertEqual(self.wall.conflict_count, 1)

    def test_negative_distance_also_counts_as_conflict(self):
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall.id, "constraint_type": "window",
            "distance_from_left_mm": -50, "width_mm": 300,
        })
        self.wall.invalidate_recordset()
        self.assertTrue(self.wall.has_conflicts)
        self.assertEqual(self.wall.conflict_count, 1)

    def test_grow_wall_clears_the_overrun(self):
        constraint = self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall.id, "constraint_type": "sink",
            "distance_from_left_mm": 2800, "width_mm": 600,
        })
        self.wall.invalidate_recordset()
        self.assertTrue(self.wall.has_conflicts)
        self.assertEqual(self.wall.conflict_count, 1)

        # Grow the wall to 3500mm — 2800 + 600 = 3400 <= 3500, now fits.
        self.wall.write({"length_mm": 3500})
        self.wall.invalidate_recordset()
        self.assertFalse(self.wall.has_conflicts)
        self.assertEqual(self.wall.conflict_count, 0)
        self.assertFalse(self.wall.has_constraint_out_of_bounds)
        self.assertTrue(constraint.exists())  # unchanged, just re-evaluated

    def test_shrink_wall_re_triggers_the_overrun(self):
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall.id, "constraint_type": "sink",
            "distance_from_left_mm": 2800, "width_mm": 600,
        })
        # Start clean: grow first so the fixture begins in a fitting state.
        self.wall.write({"length_mm": 3500})
        self.wall.invalidate_recordset()
        self.assertFalse(self.wall.has_conflicts)

        # Shrink to 2590mm (the exact QA repro value) — 2800 + 600 = 3400
        # now overruns by 810mm.
        self.wall.write({"length_mm": 2590})
        self.wall.invalidate_recordset()
        self.assertTrue(self.wall.has_conflicts)
        self.assertTrue(self.wall.has_constraint_out_of_bounds)
        self.assertEqual(self.wall.conflict_count, 1)

    def test_clean_wall_well_placed_constraint_zero_conflicts(self):
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall.id, "constraint_type": "window",
            "distance_from_left_mm": 300, "width_mm": 900,
        })
        self.wall.invalidate_recordset()
        self.assertFalse(self.wall.has_conflicts)
        self.assertFalse(self.wall.has_constraint_out_of_bounds)
        self.assertFalse(self.wall.has_constraint_overlap)
        self.assertEqual(self.wall.conflict_count, 0)

    def test_conflict_count_deduplicates_multi_reason_constraint(self):
        # A single constraint that is BOTH out-of-bounds AND overlapping
        # another constraint must still count once, not twice — the field
        # tallies distinct conflicting constraints, not conflict reasons.
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall.id, "constraint_type": "window",
            "distance_from_left_mm": 2600, "width_mm": 900,
        })
        overrunning_overlapper = self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall.id, "constraint_type": "sink",
            # Overlaps the window above (2700-3300 vs 2600-3500) AND
            # overruns the 3000mm wall (2700 + 800 = 3500 > 3000).
            "distance_from_left_mm": 2700, "width_mm": 800,
        })
        self.wall.invalidate_recordset()
        self.assertTrue(self.wall.has_constraint_out_of_bounds)
        self.assertTrue(self.wall.has_constraint_overlap)
        # window (overlap only) + sink (overlap + oob, counted once) = 2.
        self.assertEqual(self.wall.conflict_count, 2)
        self.assertTrue(overrunning_overlapper.exists())

    def test_conflict_count_counts_cabinet_collision_constraints(self):
        # A cabinet line colliding with an in-bounds, non-overlapping
        # constraint must still contribute to conflict_count via the
        # pre-existing cabinet-vs-constraint collision path.
        product = self.env["product.product"].create({
            "name": "Test Cabinet SB-BASE-2DR",
            "default_code": "SB-BASE-2DR-CC-TEST",
            "type": "consu",
            "list_price": 500.0,
        })
        self.env["southbrook.room.constraint"].create({
            "wall_id": self.wall.id, "constraint_type": "window",
            "distance_from_left_mm": 1000, "width_mm": 600,
        })
        self.env["sale.order.line"].create({
            "order_id": self.order.id, "product_id": product.id,
            "product_uom_qty": 1.0,
            "name": "Test SB-BASE-2DR line",
            "wall_id": self.wall.id, "position_from_left_mm": 900,
        })
        self.wall.invalidate_recordset()
        self.assertTrue(self.wall.has_conflicts)
        self.assertEqual(self.wall.conflict_count, 1)
