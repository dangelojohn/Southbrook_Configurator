# SPDX-License-Identifier: LGPL-3.0-only
"""Commit-5 tests: workorder tool consumption side-effects on asset life."""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools", "consumption")
class TestWorkorderToolConsumption(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Consumption = cls.env["southbrook.workorder.tool.consumption"]
        cls.Asset = cls.env["southbrook.tool.asset"]
        cls.Crib = cls.env["southbrook.tool.crib"]
        cls.Product = cls.env["product.product"]
        cls.Workcenter = cls.env["mrp.workcenter"]

        cls.cat_blade = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_blade_melamine"
        )

        cls.wc = cls.Workcenter.create({
            "name": "Consumption-test WC",
            "code": "TWC-CONS",
        })
        cls.crib = cls.Crib.create({
            "code": "UTEST-CRIB-CONS",
            "name": "Consumption test crib",
        })

        cls.tool_product = cls.Product.create({
            "name": "CONS tool product",
            "default_code": "UTEST-TOOL-CONS",
            "type": "consu",
            "x_southbrook_is_tool": True,
            "x_southbrook_is_reusable_tool": True,
            "x_southbrook_tool_category_id": cls.cat_blade.id,
        })

    def _new_asset(self, **kw):
        vals = {
            "name": "CONS asset",
            "product_id": self.tool_product.id,
            "tool_crib_id": self.crib.id,
            "workcenter_id": self.wc.id,
            "lifecycle_state": "in_use",
            "condition": "good",
            "estimated_life_qty": 100.0,
            "remaining_life_qty": 100.0,
            "life_unit": "cuts",
        }
        vals.update(kw)
        return self.Asset.create(vals)

    def _new_workorder(self):
        Product = self.env["product.product"]
        Bom = self.env["mrp.bom"]
        Production = self.env["mrp.production"]
        finished = Product.create({
            "name": "CONS finished",
            "default_code": "UTEST-FINISHED-CONS",
            "type": "consu",
            "is_storable": True,
        })
        component = Product.create({
            "name": "CONS component",
            "default_code": "UTEST-COMP-CONS",
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
                "name": "CONS op",
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

    def test_consumption_reduces_remaining_life(self):
        asset = self._new_asset()
        wo = self._new_workorder()
        self.Consumption.create({
            "workorder_id": wo.id,
            "asset_id": asset.id,
            "quantity": 25.0,
        })
        self.assertEqual(asset.remaining_life_qty, 75.0)
        self.assertEqual(asset.total_usage_qty, 25.0)
        self.assertEqual(asset.last_used_workorder_id, wo)

    def test_consumption_flips_to_needs_sharpening_at_zero_life(self):
        asset = self._new_asset(remaining_life_qty=10.0)
        wo = self._new_workorder()
        self.Consumption.create({
            "workorder_id": wo.id,
            "asset_id": asset.id,
            "quantity": 15.0,  # exceeds remaining_life
        })
        self.assertEqual(asset.remaining_life_qty, 0.0)
        self.assertEqual(asset.lifecycle_state, "needs_sharpening")

    def test_total_cost_compute(self):
        asset = self._new_asset()
        wo = self._new_workorder()
        cons = self.Consumption.create({
            "workorder_id": wo.id,
            "asset_id": asset.id,
            "quantity": 4.0,
            "unit_cost": 2.5,
        })
        self.assertEqual(cons.total_cost, 10.0)
