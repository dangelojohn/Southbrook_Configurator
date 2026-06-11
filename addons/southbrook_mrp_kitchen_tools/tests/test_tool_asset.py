# SPDX-License-Identifier: LGPL-3.0-only
"""Commit-2 tests: tool asset lifecycle, availability, transitions, maintenance.equipment link."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools", "tool_asset")
class TestToolAsset(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Asset = cls.env["southbrook.tool.asset"]
        cls.Product = cls.env["product.product"]
        cls.Crib = cls.env["southbrook.tool.crib"]
        cls.Equipment = cls.env["maintenance.equipment"]
        cls.Cat = cls.env["southbrook.tool.category"]

        cls.cat_blade = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_blade_melamine"
        )
        cls.tool_product = cls.Product.create({
            "name": "Unit-test tool product",
            "default_code": "UTEST-TOOL-PROD",
            "type": "consu",
            "x_southbrook_is_tool": True,
            "x_southbrook_is_reusable_tool": True,
            "x_southbrook_tool_category_id": cls.cat_blade.id,
        })
        cls.crib = cls.Crib.create({
            "code": "UTEST-CRIB-ASSET",
            "name": "Asset test crib",
        })

    def _new_asset(self, name="UT Asset", **kw):
        vals = {
            "name": name,
            "product_id": self.tool_product.id,
            "tool_crib_id": self.crib.id,
        }
        vals.update(kw)
        return self.Asset.create(vals)

    # ─── Creation / defaults ────────────────────────────────────────────

    def test_default_lifecycle_state_is_available(self):
        a = self._new_asset()
        self.assertEqual(a.lifecycle_state, "available")
        self.assertTrue(a.is_available)

    def test_code_auto_assigned_from_sequence(self):
        a = self._new_asset()
        self.assertTrue(a.code and a.code.startswith("SBK-TA"))

    def test_product_must_be_tool(self):
        non_tool = self.Product.create({
            "name": "Not a tool",
            "default_code": "UTEST-NON-TOOL",
            "type": "consu",
        })
        with self.assertRaises(ValidationError):
            self.Asset.create({
                "name": "Bad asset",
                "product_id": non_tool.id,
            })

    # ─── State transitions ─────────────────────────────────────────────

    def test_mark_available_then_in_use(self):
        a = self._new_asset()
        a.action_mark_available()
        self.assertEqual(a.lifecycle_state, "available")
        self.assertTrue(a.is_available)
        a.action_mark_in_use()
        self.assertEqual(a.lifecycle_state, "in_use")
        self.assertFalse(a.is_available)

    def test_mark_needs_sharpening(self):
        a = self._new_asset(lifecycle_state="available")
        a.action_mark_needs_sharpening()
        self.assertEqual(a.lifecycle_state, "needs_sharpening")
        self.assertFalse(a.is_available)

    def test_mark_needs_calibration(self):
        a = self._new_asset(lifecycle_state="available")
        a.action_mark_needs_calibration()
        self.assertEqual(a.lifecycle_state, "needs_calibration")
        self.assertFalse(a.is_available)

    def test_mark_broken_blocks_availability(self):
        a = self._new_asset(lifecycle_state="available")
        a.action_mark_broken()
        self.assertEqual(a.lifecycle_state, "broken")
        self.assertFalse(a.is_available)

    def test_retire_blocks_availability(self):
        a = self._new_asset(lifecycle_state="available")
        a.action_retire()
        self.assertEqual(a.lifecycle_state, "retired")
        self.assertFalse(a.is_available)

    # ─── Condition affects availability ────────────────────────────────

    def test_damaged_condition_blocks_availability(self):
        a = self._new_asset(lifecycle_state="available", condition="damaged")
        self.assertFalse(a.is_available)

    def test_unsafe_condition_blocks_availability(self):
        a = self._new_asset(lifecycle_state="available", condition="unsafe")
        self.assertFalse(a.is_available)

    def test_dull_condition_is_available_but_flagged(self):
        a = self._new_asset(lifecycle_state="available", condition="dull")
        # Dull means it CAN cut, just inefficiently — still available
        self.assertTrue(a.is_available)

    # ─── maintenance.equipment linkage ─────────────────────────────────

    def test_equipment_back_reference(self):
        equip = self.Equipment.create({
            "name": "Linked equipment for asset test",
        })
        a = self._new_asset(equipment_id=equip.id)
        self.assertIn(a, equip.southbrook_tool_asset_ids)
        self.assertGreaterEqual(equip.southbrook_tool_asset_count, 1)

    # ─── Demo-data sanity ──────────────────────────────────────────────

    def test_demo_dull_blade_is_in_needs_sharpening(self):
        ref = self.env.ref
        dull = ref(
            "southbrook_mrp_kitchen_tools.asset_blade_mel_02",
            raise_if_not_found=False,
        )
        if dull:
            self.assertEqual(dull.lifecycle_state, "needs_sharpening")
            self.assertEqual(dull.condition, "dull")

    def test_demo_damaged_cnc_bit_is_under_maintenance(self):
        ref = self.env.ref
        broken = ref(
            "southbrook_mrp_kitchen_tools.asset_cnc_down_3mm_01",
            raise_if_not_found=False,
        )
        if broken:
            self.assertEqual(broken.lifecycle_state, "under_maintenance")
            self.assertFalse(broken.is_available)

    def test_demo_caliper_calibration_dates(self):
        ref = self.env.ref
        cal = ref(
            "southbrook_mrp_kitchen_tools.asset_caliper_01",
            raise_if_not_found=False,
        )
        if cal:
            self.assertTrue(cal.last_calibrated_date)
            self.assertTrue(cal.next_calibration_due_date)
