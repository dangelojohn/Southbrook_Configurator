# SPDX-License-Identifier: LGPL-3.0-only
"""M1 master-data sanity — material + finish seeds load with the right
counts, codes are unique, and the boolean capability flags carry the
business intent the duration formulas (M2) will read from."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "m1")
class TestMasterData(TransactionCase):

    def test_10_materials_seeded(self):
        Material = self.env["southbrook.kitchen.material"]
        self.assertEqual(
            Material.search_count([]), 10,
            "Expected exactly 10 seeded materials.",
        )

    def test_9_finishes_seeded(self):
        Finish = self.env["southbrook.kitchen.finish"]
        self.assertEqual(
            Finish.search_count([]), 9,
            "Expected exactly 9 seeded finishes.",
        )

    def test_material_codes_unique(self):
        codes = self.env["southbrook.kitchen.material"].search([]).mapped("code")
        self.assertEqual(
            len(codes), len(set(codes)),
            "Material codes must be unique."
        )

    def test_finish_codes_unique(self):
        codes = self.env["southbrook.kitchen.finish"].search([]).mapped("code")
        self.assertEqual(
            len(codes), len(set(codes)),
            "Finish codes must be unique."
        )

    def test_stone_quartz_solid_surface_default_subcontract(self):
        """The three countertop substrates default to subcontract."""
        for code in ("quartz", "stone", "solid_surface"):
            mat = self.env.ref(
                f"southbrook_mrp_kitchen_workcenters.material_{code}")
            self.assertTrue(
                mat.is_subcontract_default,
                f"{code} should default to subcontract")
            self.assertFalse(
                mat.can_be_edge_banded,
                f"{code} should not be edge_banded")

    def test_solid_wood_not_edge_banded_but_finished(self):
        mat = self.env.ref(
            "southbrook_mrp_kitchen_workcenters.material_solid_wood")
        self.assertFalse(mat.can_be_edge_banded)
        self.assertTrue(mat.requires_finishing)

    def test_painted_lacquered_high_gloss_route_through_booth(self):
        """The wet finishes drive cure-time buffer + paint-booth routing."""
        for code, min_cure in (
            ("painted", 360),
            ("lacquered", 300),
            ("high_gloss", 480),
        ):
            f = self.env.ref(
                f"southbrook_mrp_kitchen_workcenters.finish_{code}")
            self.assertTrue(f.requires_sanding, f"{code} should require sanding")
            self.assertTrue(f.requires_paint_booth,
                            f"{code} should route through paint booth")
            self.assertEqual(
                f.cure_time_buffer_min, min_cure,
                f"{code}: expected {min_cure} min cure, got {f.cure_time_buffer_min}",
            )

    def test_raw_melamine_laminate_skip_finishing_path(self):
        """Non-wet finishes have zero cure buffer and skip sanding/booth."""
        for code in ("raw", "melamine", "laminate"):
            f = self.env.ref(
                f"southbrook_mrp_kitchen_workcenters.finish_{code}")
            self.assertFalse(f.requires_sanding)
            self.assertFalse(f.requires_paint_booth)
            self.assertEqual(f.cure_time_buffer_min, 0)
