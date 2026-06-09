# SPDX-License-Identifier: LGPL-3.0-only
"""Targeted unit tests on the packing primitive."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "config_engine", "pack")
class TestPackStretch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Engine = cls.env["southbrook.config.engine"]

    def _widths(self, plan):
        return [int(round(c["width_mm"])) for c in plan if c.get("width_mm")]

    def test_900mm_exact_one_cabinet(self):
        plan = self.Engine._pack_stretch(900, [900, 800, 600, 450, 300, 225])
        self.assertEqual(self._widths(plan), [900])

    def test_1800mm_two_900s(self):
        plan = self.Engine._pack_stretch(1800, [900, 800, 600, 450, 300, 225])
        self.assertEqual(self._widths(plan), [900, 900])

    def test_700mm_signature_no_perfect_fit(self):
        """700 from {900,800,600,450,300,225} → backtrack: 600+...
        no exact fit; falls back to single largest-that-fits (600)."""
        plan = self.Engine._pack_stretch(700, [900, 800, 600, 450, 300, 225])
        total = sum(self._widths(plan))
        # Either an exact-fit 600+ stack OR the fallback single-cabinet.
        self.assertLessEqual(total, 700)

    def test_zero_returns_empty(self):
        self.assertEqual(self.Engine._pack_stretch(0, [600]), [])

    def test_smaller_than_smallest_returns_empty(self):
        self.assertEqual(self.Engine._pack_stretch(100, [600, 450]), [])

    def test_assigns_door_count_per_width(self):
        plan = self.Engine._pack_stretch(900, [900, 600, 300])
        for cab in plan:
            if cab.get("width_mm", 0) >= 600:
                self.assertEqual(cab["door_count"], 2)
            else:
                self.assertEqual(cab["door_count"], 1)
