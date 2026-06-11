# SPDX-License-Identifier: LGPL-3.0-only
"""Foundation seed integrity — the 11-section A..K category tree is
present, each top-level root carries the right tool_family / directness,
the parent / child hierarchy resolves, and complete_name computes.
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools",
        "categories")
class TestCategoriesSeed(TransactionCase):

    def _ref(self, xmlid):
        return self.env.ref(f"southbrook_mrp_kitchen_tools.{xmlid}")

    # ──────────────────────────────────────────────────────────────────
    # All 11 root categories exist
    # ──────────────────────────────────────────────────────────────────
    def test_all_eleven_roots_present(self):
        roots = [
            "cat_cutting_tools",
            "cat_fasteners_assembly",
            "cat_adhesives",
            "cat_abrasives",
            "cat_finishing",
            "cat_measuring",
            "cat_clamps_jigs",
            "cat_hand_tools",
            "cat_maintenance",
            "cat_safety",
            "cat_packing",
        ]
        for xmlid in roots:
            rec = self._ref(xmlid)
            self.assertTrue(rec, f"Missing root category: {xmlid}")
            self.assertFalse(
                rec.parent_id,
                f"{xmlid} should be a top-level root, not a child of "
                f"{rec.parent_id.name}",
            )

    # ──────────────────────────────────────────────────────────────────
    # Subtree counts — each section seeds a meaningful number of leaves
    # ──────────────────────────────────────────────────────────────────
    def test_saw_blade_subtree(self):
        saw = self._ref("cat_saw_blades")
        self.assertEqual(saw.tool_family, "saw_blade")
        self.assertTrue(saw.reusable)
        self.assertTrue(saw.requires_sharpening)
        # At least 8 blade subtypes seeded.
        self.assertGreaterEqual(len(saw.child_ids), 8)

    def test_cnc_bit_subtree(self):
        cnc = self._ref("cat_cnc_bits")
        self.assertEqual(cnc.tool_family, "cnc_router_bit")
        self.assertTrue(cnc.reusable)
        self.assertGreaterEqual(len(cnc.child_ids), 10)

    def test_adhesives_have_expiry_and_hazard(self):
        adh = self._ref("cat_adhesives")
        self.assertTrue(adh.has_expiry_date)
        self.assertTrue(adh.hazardous)
        self.assertTrue(adh.msds_required)
        self.assertTrue(adh.requires_lot_tracking)

    def test_safety_directness(self):
        safety = self._ref("cat_safety")
        self.assertEqual(safety.directness, "safety_supply")
        self.assertEqual(safety.tool_family, "safety_ppe")

    def test_maintenance_directness(self):
        maint = self._ref("cat_maintenance")
        self.assertEqual(maint.directness, "maintenance_supply")

    # ──────────────────────────────────────────────────────────────────
    # complete_name traverses parents
    # ──────────────────────────────────────────────────────────────────
    def test_complete_name_includes_parents(self):
        panel = self._ref("cat_blade_panel")
        self.assertEqual(
            panel.complete_name,
            "Cutting Tools / Saw Blades / Panel Saw Blades",
        )

    def test_complete_name_two_levels(self):
        screws = self._ref("cat_screws")
        self.assertEqual(
            screws.complete_name,
            "Fasteners and Assembly Consumables / Screws",
        )

    # ──────────────────────────────────────────────────────────────────
    # Constraints
    # ──────────────────────────────────────────────────────────────────
    def test_no_self_parent_recursion(self):
        # Odoo 19's _parent_store_update raises UserError on self-cycle
        # — it intercepts before our @api.constrains can fire.
        cat = self._ref("cat_saw_blades")
        with self.assertRaises(UserError):
            cat.parent_id = cat

    def test_reusable_xor_consumable(self):
        with self.assertRaises(ValidationError):
            self.env["southbrook.tool.category"].create({
                "name": "Bad both",
                "reusable": True,
                "consumable": True,
            })

    def test_code_unique(self):
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env["southbrook.tool.category"].create({
                    "name": "Collision",
                    "code": "CUTTING",
                })

    # ──────────────────────────────────────────────────────────────────
    # Onchange parent inherits family/directness
    # ──────────────────────────────────────────────────────────────────
    def test_onchange_parent_inherits_family(self):
        new = self.env["southbrook.tool.category"].new({
            "name": "Test child",
            "parent_id": self._ref("cat_saw_blades").id,
        })
        new._onchange_parent_inherits_family()
        self.assertEqual(new.tool_family, "saw_blade")
