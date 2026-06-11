# SPDX-License-Identifier: LGPL-3.0-only
"""Commit-4 tests: workorder readiness gate against tool availability."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools", "readiness")
class TestWorkorderToolReadiness(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Asset = cls.env["southbrook.tool.asset"]
        cls.Crib = cls.env["southbrook.tool.crib"]
        cls.Product = cls.env["product.product"]
        cls.Workcenter = cls.env["mrp.workcenter"]
        cls.WCReq = cls.env["southbrook.workcenter.tool.requirement"]

        cls.cat_blade = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_blade_melamine"
        )

        cls.wc = cls.Workcenter.create({
            "name": "Readiness-test WC",
            "code": "TWC-RDY",
        })
        cls.crib = cls.Crib.create({
            "code": "UTEST-CRIB-RDY",
            "name": "Readiness test crib",
            "workcenter_ids": [(6, 0, [cls.wc.id])],
        })

        cls.tool_product = cls.Product.create({
            "name": "RDY tool product",
            "default_code": "UTEST-TOOL-RDY",
            "type": "consu",
            "x_southbrook_is_tool": True,
            "x_southbrook_is_reusable_tool": True,
            "x_southbrook_tool_category_id": cls.cat_blade.id,
        })

    # Helpers ─────────────────────────────────────────────────────────

    def _new_asset(self, **kw):
        vals = {
            "name": "RDY asset",
            "product_id": self.tool_product.id,
            "tool_crib_id": self.crib.id,
            "workcenter_id": self.wc.id,
            "lifecycle_state": "available",
            "condition": "good",
        }
        vals.update(kw)
        return self.Asset.create(vals)

    def _new_requirement(self, qty=1, mandatory=True):
        return self.WCReq.create({
            "workcenter_id": self.wc.id,
            "tool_category_id": self.cat_blade.id,
            "quantity": qty,
            "is_mandatory": mandatory,
        })

    def _new_workorder(self):
        """Minimal mrp.workorder for readiness — built directly so we don't
        need a full mrp.production/bom in test scope."""
        # Build a minimal BoM + product to materialise a workorder
        Product = self.env["product.product"]
        Bom = self.env["mrp.bom"]
        Production = self.env["mrp.production"]

        finished = Product.create({
            "name": "RDY finished",
            "default_code": "UTEST-FINISHED-RDY",
            "type": "consu",
            "is_storable": True,
        })
        component = Product.create({
            "name": "RDY component",
            "default_code": "UTEST-COMP-RDY",
            "type": "consu",
            "is_storable": True,
        })
        bom = Bom.create({
            "product_tmpl_id": finished.product_tmpl_id.id,
            "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {
                "product_id": component.id, "product_qty": 1.0,
            })],
            "operation_ids": [(0, 0, {
                "name": "RDY op",
                "workcenter_id": self.wc.id,
                "time_cycle_manual": 1.0,
            })],
        })
        mo = Production.create({
            "product_id": finished.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        mo.action_confirm()
        return mo.workorder_ids[:1]

    # Tests ───────────────────────────────────────────────────────────

    def test_default_readiness_is_not_checked(self):
        wo = self._new_workorder()
        self.assertEqual(wo.southbrook_tool_readiness_state, "not_checked")

    def test_ready_when_required_asset_available(self):
        self._new_requirement(qty=1)
        self._new_asset()
        wo = self._new_workorder()
        wo.action_check_tool_readiness()
        self.assertEqual(wo.southbrook_tool_readiness_state, "ready")

    def test_blocked_when_no_asset_available(self):
        self._new_requirement(qty=1, mandatory=True)
        wo = self._new_workorder()
        wo.action_check_tool_readiness()
        self.assertEqual(wo.southbrook_tool_readiness_state, "blocked")

    def test_warning_when_optional_missing(self):
        self._new_requirement(qty=1, mandatory=False)
        wo = self._new_workorder()
        wo.action_check_tool_readiness()
        self.assertEqual(wo.southbrook_tool_readiness_state, "warning")

    def test_blocked_when_only_dull_blade(self):
        # Dull blade passes is_available but is needs_sharpening, blocked
        self._new_requirement(qty=1)
        self._new_asset(lifecycle_state="needs_sharpening", condition="dull")
        wo = self._new_workorder()
        wo.action_check_tool_readiness()
        self.assertEqual(wo.southbrook_tool_readiness_state, "blocked")

    def test_blocked_when_only_damaged_blade(self):
        # Damaged blade fails is_available, blocked
        self._new_requirement(qty=1)
        self._new_asset(condition="damaged")
        wo = self._new_workorder()
        wo.action_check_tool_readiness()
        self.assertEqual(wo.southbrook_tool_readiness_state, "blocked")

    def test_button_start_raises_when_blocked(self):
        self._new_requirement(qty=1)
        wo = self._new_workorder()
        wo.action_check_tool_readiness()
        self.assertEqual(wo.southbrook_tool_readiness_state, "blocked")
        with self.assertRaises(UserError):
            wo.button_start()
