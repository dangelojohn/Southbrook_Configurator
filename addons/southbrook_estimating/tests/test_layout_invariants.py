# SPDX-License-Identifier: LGPL-3.0-only
"""Topology-agnostic invariant + capacity tests for the layout engine.

Enforces the COORDINATE_CONTRACT postconditions: every emitted layout is
physically valid (in bounds, no 3D overlap, valid walls/rotations, count
conserved), and impossible layouts raise LayoutCapacityExceeded instead of
overflowing. These invariants are reused by every future topology.
"""
from odoo.tests.common import TransactionCase
from odoo.addons.southbrook_estimating.models import kitchen_layout_engine as E
from odoo.addons.southbrook_estimating.models import layout_invariants as I


def _room(w, d):
    return {"width_mm": w, "depth_mm": d, "height_mm": 2400}


def _base(n):
    return [{"id": i, "width_mm": 600, "height_mm": 876, "depth_mm": 600,
             "family": "base", "cabinet_type": "base", "zone": "base_run"}
            for i in range(1, n + 1)]


def _wall(n):
    return [{"id": 100 + i, "width_mm": 600, "height_mm": 720, "depth_mm": 320,
             "family": "wall", "cabinet_type": "wall", "zone": "wall"}
            for i in range(1, n + 1)]


class TestLayoutInvariants(TransactionCase):

    def _assert_valid(self, cabs, room, label):
        r = E.resolve_and_layout(cabs, room)
        violations = I.check_all(r, len(cabs), room)
        self.assertEqual(violations, {}, "%s: %s" % (label, violations))
        return r

    def test_invariants_straight(self):
        self._assert_valid(_base(6), _room(4000, 3000), "straight")

    def test_invariants_L(self):
        r = self._assert_valid(_base(10), _room(4000, 3000), "L-10")
        self.assertEqual(len(r["inserted"]), 1)
        self.assertEqual(len(r["removed_ids"]), 2)

    def test_invariants_small_no_corner(self):
        r = self._assert_valid(_base(3), _room(4000, 3000), "small")
        self.assertEqual(len(r["inserted"]), 0)

    def test_invariants_mixed_base_and_wall(self):
        r = self._assert_valid(_base(8) + _wall(8), _room(4000, 3000), "mixed")
        # a base corner AND a wall corner, each replacing two standards
        self.assertEqual(len(r["inserted"]), 2)
        self.assertEqual(len(r["removed_ids"]), 4)

    def test_overlap_invariant_is_3d(self):
        # base + wall stacked at same X/Z but different Y must NOT count as
        # an overlap.
        r = E.resolve_and_layout(_base(4) + _wall(4), _room(4000, 3000))
        self.assertEqual(I.check_no_overlaps(r), [])

    def test_capacity_exceeded_raises(self):
        with self.assertRaises(E.LayoutCapacityExceeded):
            E.resolve_and_layout(_base(25), _room(6000, 5000))

    def test_capacity_full_wall_cannot_seat_corner(self):
        # 18 cabinets: back wall exactly full (10*600=6000) leaves no slack
        # for the 914mm corner → explicit failure, not silent overflow.
        with self.assertRaises(E.LayoutCapacityExceeded):
            E.resolve_and_layout(_base(18), _room(6000, 5000))

    def test_check_capacity_preflight(self):
        cc = E.check_capacity(_base(25), _room(6000, 5000))
        self.assertFalse(cc["ok"])
        self.assertGreater(cc["requested_mm"], cc["capacity_mm"])

    def test_deterministic(self):
        a = E.resolve_and_layout(_base(10), _room(4000, 3000))
        b = E.resolve_and_layout(_base(10), _room(4000, 3000))
        self.assertEqual(a, b)
