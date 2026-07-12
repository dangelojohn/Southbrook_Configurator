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

    def test_negative_quantity_rejected(self):
        """H3 regression: a negative quantity is the tool-life 'un-wear' +
        negative-cost vector — it must be rejected, not applied."""
        from odoo.exceptions import ValidationError
        asset = self._new_asset(remaining_life_qty=50.0)
        wo = self._new_workorder()
        with self.assertRaises(ValidationError):
            self.Consumption.create({
                "workorder_id": wo.id,
                "asset_id": asset.id,
                "quantity": -25.0,
            })
        # The asset's life/usage must be untouched by the rejected row.
        self.assertEqual(asset.remaining_life_qty, 50.0)
        self.assertEqual(asset.total_usage_qty, 0.0)

    def test_negative_unit_cost_rejected(self):
        """H3 regression: a negative unit_cost can't deflate the MO rollup."""
        from odoo.exceptions import ValidationError
        asset = self._new_asset()
        wo = self._new_workorder()
        with self.assertRaises(ValidationError):
            self.Consumption.create({
                "workorder_id": wo.id, "asset_id": asset.id,
                "quantity": 1.0, "unit_cost": -5.0,
            })

    # ------------------------------------------------------------------
    # Acceptance — unlink restores asset life (P8 rollback 2026-06-18).
    # The latent gap surfaced during the P8 fix verify: create() debits
    # the asset but unlink() previously did not credit it back, leaving
    # the asset permanently under-counted after any consumption-row
    # cleanup (test scans, mistaken debits, manual ledger trims).
    # ------------------------------------------------------------------
    def test_unlink_restores_remaining_life_and_usage(self):
        asset = self._new_asset(
            remaining_life_qty=100.0, estimated_life_qty=100.0)
        wo = self._new_workorder()
        cons = self.Consumption.create({
            "workorder_id": wo.id,
            "asset_id": asset.id,
            "quantity": 30.0,
        })
        # Sanity — create() debited
        self.assertEqual(asset.remaining_life_qty, 70.0)
        self.assertEqual(asset.total_usage_qty, 30.0)
        self.assertEqual(asset.last_used_workorder_id, wo)

        cons.unlink()
        # Inverse should restore both fields
        self.assertEqual(
            asset.remaining_life_qty, 100.0,
            "unlink must add back the qty it debited")
        self.assertEqual(
            asset.total_usage_qty, 0.0,
            "unlink must reverse the usage bump")
        # last_used_workorder_id was pointing at THIS consumption's WO,
        # so it should clear (no remaining consumption rows for asset).
        self.assertFalse(
            asset.last_used_workorder_id,
            "no remaining consumption -> last_used_workorder cleared")
        self.assertFalse(asset.last_used_date)

    def test_unlink_caps_remaining_at_estimated_life(self):
        asset = self._new_asset(
            remaining_life_qty=80.0, estimated_life_qty=100.0,
            total_usage_qty=20.0,
        )
        wo = self._new_workorder()
        cons = self.Consumption.create({
            "workorder_id": wo.id, "asset_id": asset.id, "quantity": 30.0,
        })
        # After create: remaining=50, usage=50
        self.assertEqual(asset.remaining_life_qty, 50.0)
        cons.unlink()
        # Restoring 30 to 50 should give 80 — already below cap, no clamp
        self.assertEqual(asset.remaining_life_qty, 80.0)

    def test_unlink_does_not_flip_lifecycle_state(self):
        # Asset crossed zero life mid-create (flipped to needs_sharpening).
        # Operator marked it as sharpened back to in_use. Unlink the
        # original consumption — must NOT clobber the operator's
        # explicit state change.
        asset = self._new_asset(
            remaining_life_qty=10.0, estimated_life_qty=100.0)
        wo = self._new_workorder()
        cons = self.Consumption.create({
            "workorder_id": wo.id, "asset_id": asset.id, "quantity": 15.0,
        })
        self.assertEqual(asset.lifecycle_state, "needs_sharpening")
        asset.lifecycle_state = "in_use"  # operator action between
        cons.unlink()
        # State remains in_use — unlink only restores numeric fields
        self.assertEqual(asset.lifecycle_state, "in_use")

    def test_unlink_falls_back_to_next_most_recent_consumption(self):
        asset = self._new_asset(
            remaining_life_qty=100.0, estimated_life_qty=100.0)
        wo_first = self._new_workorder()
        wo_second = self._new_workorder()
        cons_first = self.Consumption.create({
            "workorder_id": wo_first.id, "asset_id": asset.id,
            "quantity": 10.0,
        })
        cons_second = self.Consumption.create({
            "workorder_id": wo_second.id, "asset_id": asset.id,
            "quantity": 5.0,
        })
        # last_used now points at wo_second (most recent)
        self.assertEqual(asset.last_used_workorder_id, wo_second)
        cons_second.unlink()
        # After unlink: cons_first remains; last_used should fall back to it
        self.assertEqual(
            asset.last_used_workorder_id, wo_first,
            "unlinking the most-recent consumption falls back to "
            "the next-most-recent")
