# SPDX-License-Identifier: LGPL-3.0-only
"""Commit-2 tests: tool crib basics + uniqueness + workcenter linkage."""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools", "tool_crib")
class TestToolCrib(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Crib = cls.env["southbrook.tool.crib"]
        cls.Workcenter = cls.env["mrp.workcenter"]

    def _new_crib(self, code, name="A crib", **kw):
        return self.Crib.create(dict({"code": code, "name": name}, **kw))

    def test_create_basic_crib(self):
        crib = self._new_crib("UTEST-BASIC", "Unit Test Basic Crib")
        self.assertTrue(crib.id)
        self.assertEqual(crib.code, "UTEST-BASIC")

    def test_code_unique_constraint(self):
        self._new_crib("UTEST-DUP")
        with self.assertRaises(Exception):
            self._new_crib("UTEST-DUP", "duplicate")

    def test_workcenter_linkage_m2m(self):
        wc = self.Workcenter.create({
            "name": "Test WC for crib linkage",
            "code": "TWC-CRIB",
        })
        crib = self._new_crib(
            "UTEST-WC", "Workcenter linkage test crib",
            workcenter_ids=[(6, 0, [wc.id])],
        )
        self.assertIn(wc, crib.workcenter_ids)

    def test_asset_count_is_zero_for_empty_crib(self):
        crib = self._new_crib("UTEST-EMPTY", "Empty crib")
        self.assertEqual(crib.asset_count, 0)

    def test_demo_cribs_present(self):
        """Sanity-check that the 12 demo cribs ship with the module."""
        ref = self.env.ref
        main = ref("southbrook_mrp_kitchen_tools.crib_main",
                   raise_if_not_found=False)
        if not main:
            self.skipTest("demo data not loaded (--without-demo=all)")
        expected_xmlids = [
            "southbrook_mrp_kitchen_tools.crib_main",
            "southbrook_mrp_kitchen_tools.crib_cut",
            "southbrook_mrp_kitchen_tools.crib_cnc",
            "southbrook_mrp_kitchen_tools.crib_edge",
            "southbrook_mrp_kitchen_tools.crib_drill",
            "southbrook_mrp_kitchen_tools.crib_sand",
            "southbrook_mrp_kitchen_tools.crib_paint",
            "southbrook_mrp_kitchen_tools.crib_assy",
            "southbrook_mrp_kitchen_tools.crib_hardware",
            "southbrook_mrp_kitchen_tools.crib_qc",
            "southbrook_mrp_kitchen_tools.crib_maint",
            "southbrook_mrp_kitchen_tools.crib_pack",
        ]
        for xid in expected_xmlids:
            crib = ref(xid, raise_if_not_found=False)
            self.assertTrue(crib, f"Demo crib missing: {xid}")
