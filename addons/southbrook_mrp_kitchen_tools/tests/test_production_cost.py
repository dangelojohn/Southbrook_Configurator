# SPDX-License-Identifier: LGPL-3.0-only
"""Commit-6 tests: mrp.production tool cost rollup + cron maintenance sweep."""
from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools", "cost_rollup")
class TestProductionToolCostRollup(TransactionCase):

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
            "name": "Cost-rollup test WC",
            "code": "TWC-COST",
        })
        cls.crib = cls.Crib.create({
            "code": "UTEST-CRIB-COST",
            "name": "Cost test crib",
        })
        cls.tool_product = cls.Product.create({
            "name": "COST tool product",
            "default_code": "UTEST-TOOL-COST",
            "type": "consu",
            "x_southbrook_is_tool": True,
            "x_southbrook_is_reusable_tool": True,
            "x_southbrook_tool_category_id": cls.cat_blade.id,
        })

    def _new_asset(self, **kw):
        vals = {
            "name": "COST asset",
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

    def _new_workorder_and_mo(self):
        Product = self.env["product.product"]
        Bom = self.env["mrp.bom"]
        Production = self.env["mrp.production"]
        finished = Product.create({
            "name": "COST finished",
            "default_code": "UTEST-FINISHED-COST",
            "type": "consu",
            "is_storable": True,
        })
        component = Product.create({
            "name": "COST component",
            "default_code": "UTEST-COMP-COST",
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
                "name": "COST op",
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
        return mo, mo.workorder_ids[:1]

    def test_cost_rollup_zero_when_no_consumption(self):
        mo, _ = self._new_workorder_and_mo()
        self.assertEqual(mo.southbrook_tool_consumption_count, 0)
        self.assertEqual(mo.southbrook_tool_consumption_cost, 0.0)

    def test_cost_rollup_sums_multiple_rows(self):
        asset = self._new_asset()
        mo, wo = self._new_workorder_and_mo()
        self.Consumption.create({
            "workorder_id": wo.id,
            "asset_id": asset.id,
            "quantity": 2.0,
            "unit_cost": 10.0,
        })
        self.Consumption.create({
            "workorder_id": wo.id,
            "asset_id": asset.id,
            "quantity": 5.0,
            "unit_cost": 3.0,
        })
        mo.invalidate_recordset()
        self.assertEqual(mo.southbrook_tool_consumption_count, 2)
        self.assertEqual(mo.southbrook_tool_consumption_cost, 35.0)


@tagged("post_install", "-at_install", "southbrook", "kitchen_tools", "cron_sweep")
class TestMaintenanceSweepCron(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Asset = cls.env["southbrook.tool.asset"]
        cls.Crib = cls.env["southbrook.tool.crib"]
        cls.Product = cls.env["product.product"]
        cls.cat_blade = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_blade_melamine"
        )
        cls.cat_caliper = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_meas_caliper"
        )
        cls.crib = cls.Crib.create({
            "code": "UTEST-CRIB-CRON",
            "name": "Cron test crib",
        })
        cls.blade_product = cls.Product.create({
            "name": "CRON blade",
            "default_code": "UTEST-CRON-BLADE",
            "type": "consu",
            "x_southbrook_is_tool": True,
            "x_southbrook_is_reusable_tool": True,
            "x_southbrook_tool_category_id": cls.cat_blade.id,
        })
        cls.caliper_product = cls.Product.create({
            "name": "CRON caliper",
            "default_code": "UTEST-CRON-CALIPER",
            "type": "consu",
            "x_southbrook_is_tool": True,
            "x_southbrook_is_reusable_tool": True,
            "x_southbrook_tool_category_id": cls.cat_caliper.id,
        })

    def test_sharpening_overdue_flips_to_needs_sharpening(self):
        yesterday = date.today() - timedelta(days=1)
        blade = self.Asset.create({
            "name": "Overdue-sharpening blade",
            "product_id": self.blade_product.id,
            "tool_crib_id": self.crib.id,
            "lifecycle_state": "available",
            "condition": "good",
            "next_sharpening_due_date": yesterday,
        })
        self.Asset._cron_maintenance_sweep()
        blade.invalidate_recordset()
        self.assertEqual(blade.lifecycle_state, "needs_sharpening")

    def test_calibration_overdue_flips_to_needs_calibration(self):
        yesterday = date.today() - timedelta(days=1)
        caliper = self.Asset.create({
            "name": "Overdue-calibration caliper",
            "product_id": self.caliper_product.id,
            "tool_crib_id": self.crib.id,
            "lifecycle_state": "available",
            "condition": "good",
            "next_calibration_due_date": yesterday,
        })
        self.Asset._cron_maintenance_sweep()
        caliper.invalidate_recordset()
        self.assertEqual(caliper.lifecycle_state, "needs_calibration")

    def test_sweep_does_not_stomp_under_maintenance(self):
        yesterday = date.today() - timedelta(days=1)
        blade = self.Asset.create({
            "name": "Already under maintenance",
            "product_id": self.blade_product.id,
            "tool_crib_id": self.crib.id,
            "lifecycle_state": "under_maintenance",
            "condition": "damaged",
            "next_sharpening_due_date": yesterday,
        })
        self.Asset._cron_maintenance_sweep()
        blade.invalidate_recordset()
        self.assertEqual(blade.lifecycle_state, "under_maintenance")

    def test_sweep_skips_assets_without_due_date(self):
        blade = self.Asset.create({
            "name": "No due date blade",
            "product_id": self.blade_product.id,
            "tool_crib_id": self.crib.id,
            "lifecycle_state": "available",
            "condition": "good",
        })
        self.Asset._cron_maintenance_sweep()
        blade.invalidate_recordset()
        self.assertEqual(blade.lifecycle_state, "available")
