# SPDX-License-Identifier: LGPL-3.0-only
"""Commit-3 tests: workcenter + operation tool requirements, tool kits."""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools", "requirements")
class TestWorkcenterToolRequirement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WCReq = cls.env["southbrook.workcenter.tool.requirement"]
        cls.Workcenter = cls.env["mrp.workcenter"]
        cls.cat_blade = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_blade_melamine"
        )
        cls.wc = cls.Workcenter.create({
            "name": "Test WC for requirement",
            "code": "TWC-REQ",
        })

    def test_create_category_requirement(self):
        req = self.WCReq.create({
            "workcenter_id": self.wc.id,
            "tool_category_id": self.cat_blade.id,
            "quantity": 2,
        })
        self.assertEqual(req.workcenter_id, self.wc)
        self.assertEqual(req.quantity, 2)
        self.assertTrue(req.is_mandatory)

    def test_requirement_must_have_category_or_product(self):
        with self.assertRaises(ValidationError):
            self.WCReq.create({
                "workcenter_id": self.wc.id,
                "quantity": 1,
            })

    def test_quantity_check(self):
        with self.assertRaises(Exception):
            self.WCReq.create({
                "workcenter_id": self.wc.id,
                "tool_category_id": self.cat_blade.id,
                "quantity": 0,
            })

    def test_back_ref_count(self):
        self.WCReq.create({
            "workcenter_id": self.wc.id,
            "tool_category_id": self.cat_blade.id,
        })
        self.WCReq.create({
            "workcenter_id": self.wc.id,
            "tool_category_id": self.cat_blade.id,
        })
        self.wc.invalidate_recordset()
        self.assertGreaterEqual(self.wc.southbrook_tool_requirement_count, 2)


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools", "tool_kit")
class TestToolKit(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Kit = cls.env["southbrook.tool.kit"]
        cls.KitLine = cls.env["southbrook.tool.kit.line"]
        cls.cat_blade = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_blade_melamine"
        )
        cls.cat_torque = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_hand_torque"
        )

    def test_create_basic_kit(self):
        kit = self.Kit.create({
            "code": "UTEST-KIT-A",
            "name": "Unit-test kit A",
            "line_ids": [
                (0, 0, {"tool_category_id": self.cat_blade.id, "quantity": 1}),
                (0, 0, {"tool_category_id": self.cat_torque.id, "quantity": 1}),
            ],
        })
        self.assertEqual(kit.line_count, 2)

    def test_kit_code_unique(self):
        self.Kit.create({"code": "UTEST-KIT-DUP", "name": "first"})
        with self.assertRaises(Exception):
            self.Kit.create({"code": "UTEST-KIT-DUP", "name": "second"})
