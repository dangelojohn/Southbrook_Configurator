# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 2.2 — practical-intelligence loop tests.

Covers the four behaviours hung off ``mrp.workorder.button_finish`` in
``southbrook_premium_orchestration``:

    1. Tool lifecycle is debited correctly when a WO finishes.
    2. Duration is backfilled from real start/end timestamps when the
       operator never punched the clock.
    3. The whole lifecycle debit is idempotent — running twice does not
       create a second ledger row or double-debit the asset.
    4. When an asset's remaining life crosses the 10% threshold, a
       'Sharpening / Replacement Due' mail.activity is scheduled.

We exercise the SBK hooks directly (``_sbk_debit_tool_lifecycle`` /
``_sbk_record_duration_if_zero``) rather than driving Odoo's full
``button_finish`` state machine, because the latter requires a
fully-staged production order with quants and qty_producing and is
already covered by upstream mrp tests. What we care about here is that
our hooks behave correctly given a finished work order; super()'s
state-machine plumbing is out of scope.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "premium_orchestration",
        "phase2_practical_loop")
class TestPhase2PracticalLoop(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Asset = cls.env["southbrook.tool.asset"]
        cls.Crib = cls.env["southbrook.tool.crib"]
        cls.OpReq = cls.env["southbrook.operation.tool.requirement"]
        cls.Consumption = cls.env["southbrook.workorder.tool.consumption"]
        cls.Product = cls.env["product.product"]
        cls.Workcenter = cls.env["mrp.workcenter"]
        cls.Bom = cls.env["mrp.bom"]
        cls.Production = cls.env["mrp.production"]
        cls.Activity = cls.env["mail.activity"]

        # Reuse the seeded melamine-blade category — it's part of the
        # data shipped by southbrook_mrp_kitchen_tools so we don't have
        # to fabricate a category tree.
        cls.category = cls.env.ref(
            "southbrook_mrp_kitchen_tools.cat_blade_melamine"
        )

        # Test work-center + crib — namespaced with UTEST so a manual
        # tester scanning the DB can spot and purge them.
        cls.workcenter = cls.Workcenter.create({
            "name": "Phase2 practical loop WC",
            "code": "UTEST-WC-P2",
        })
        cls.crib = cls.Crib.create({
            "code": "UTEST-CRIB-P2",
            "name": "Phase2 practical loop crib",
        })

        # Tool product (flagged as a Southbrook tool, reusable).
        cls.tool_product = cls.Product.create({
            "name": "Phase2 test blade",
            "default_code": "UTEST-BLADE-P2",
            "type": "consu",
            "x_southbrook_is_tool": True,
            "x_southbrook_is_reusable_tool": True,
            "x_southbrook_tool_category_id": cls.category.id,
        })

        # Finished + component products for the BoM.
        cls.finished = cls.Product.create({
            "name": "Phase2 finished",
            "default_code": "UTEST-FIN-P2",
            "type": "consu",
            "is_storable": True,
        })
        cls.component = cls.Product.create({
            "name": "Phase2 component",
            "default_code": "UTEST-CMP-P2",
            "type": "consu",
            "is_storable": True,
        })

    def _new_asset(self, **overrides):
        """Asset with 100/100 life, $5 purchase cost — total_cost == qty × 5."""
        vals = {
            "name": "Phase2 asset",
            "product_id": self.tool_product.id,
            "tool_crib_id": self.crib.id,
            "workcenter_id": self.workcenter.id,
            "lifecycle_state": "in_use",
            "condition": "good",
            "estimated_life_qty": 100.0,
            "remaining_life_qty": 100.0,
            "life_unit": "cuts",
            # The brief calls this ``estimated_unit_cost``; the live
            # model uses ``purchase_cost``. The hook reads either.
            "purchase_cost": 5.0,
        }
        vals.update(overrides)
        return self.Asset.create(vals)

    def _new_mo_with_wo(
        self, op_qty_per_unit=2.0, qty_produced=10.0, create_req=True,
    ):
        """Build a minimal MO with one WO whose operation requires the
        configured tool category at ``op_qty_per_unit`` per produced unit.

        Returns ``(mo, wo, op_req)``.
        """
        bom = self.Bom.create({
            "product_tmpl_id": self.finished.product_tmpl_id.id,
            "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {
                "product_id": self.component.id,
                "product_qty": 1.0,
            })],
            "operation_ids": [(0, 0, {
                "name": "Phase2 cut",
                "workcenter_id": self.workcenter.id,
                "time_cycle_manual": 1.0,
            })],
        })
        mo = self.Production.create({
            "product_id": self.finished.id,
            "product_qty": qty_produced,
            "bom_id": bom.id,
        })
        mo.action_confirm()
        wo = mo.workorder_ids[:1]
        # Wire a category-based operation tool requirement. The hook
        # resolves the requirement → asset by picking the in-service
        # asset in the category with the most remaining life.
        op_req = self.OpReq.browse()
        if create_req:
            op_req = self.OpReq.create({
                "operation_id": wo.operation_id.id,
                "tool_category_id": self.category.id,
                "quantity": 1,
                "consume_qty_per_unit": op_qty_per_unit,
            })
        # qty_produced isn't auto-set by action_confirm; the practical
        # loop multiplies it by per-unit consumption so we set it
        # explicitly.
        wo.qty_produced = qty_produced
        return mo, wo, op_req

    # ──────────────────────────────────────────────────────────────────
    # 1. Lifecycle debit happens correctly
    # ──────────────────────────────────────────────────────────────────
    def test_button_finish_debits_lifecycle(self):
        asset = self._new_asset()
        mo, wo, op_req = self._new_mo_with_wo(
            op_qty_per_unit=2.0, qty_produced=10.0,
        )

        wo._sbk_debit_tool_lifecycle()

        consumptions = self.Consumption.search([
            ("workorder_id", "=", wo.id),
        ])
        self.assertEqual(
            len(consumptions), 1,
            "Expected exactly one consumption row per resolved asset",
        )
        c = consumptions[0]
        self.assertEqual(c.asset_id, asset)
        self.assertEqual(c.quantity, 20.0,
                         "2.0/unit × 10 produced = 20")
        self.assertEqual(c.unit_cost, 5.0)
        self.assertEqual(c.total_cost, 100.0,
                         "20 × 5 = 100 (compute on consumption)")

        asset.invalidate_recordset()
        self.assertEqual(asset.remaining_life_qty, 80.0,
                         "100 − 20 = 80; consumption.create() does the debit")
        self.assertEqual(asset.total_usage_qty, 20.0)
        self.assertEqual(asset.last_used_workorder_id, wo)
        self.assertTrue(wo.sbk_lifecycle_processed)

    # ──────────────────────────────────────────────────────────────────
    # 2. Duration backfill
    # ──────────────────────────────────────────────────────────────────
    def test_button_finish_logs_duration(self):
        _mo, wo, _req = self._new_mo_with_wo()
        now = fields.Datetime.now()
        wo.write({
            "date_start": now - timedelta(minutes=10),
            "date_finished": now,
            "duration": 0.0,
        })

        wo._sbk_record_duration_if_zero()

        # 10 minutes ± half a minute — the assertion is loose because
        # the assignment of "now" and the write may straddle a second
        # boundary on slow CI.
        self.assertAlmostEqual(
            wo.duration, 10.0, delta=0.5,
            msg="duration should be derived from date_start/date_finished",
        )

    def test_duration_falls_back_to_expected_when_no_timestamps(self):
        _mo, wo, _req = self._new_mo_with_wo()
        wo.write({
            "date_start": False,
            "date_finished": False,
            "duration": 0.0,
            "duration_expected": 42.0,
        })

        wo._sbk_record_duration_if_zero()

        self.assertEqual(wo.duration, 42.0,
                         "fall back to duration_expected when no timestamps")

    def test_duration_unchanged_when_operator_logged_time(self):
        _mo, wo, _req = self._new_mo_with_wo()
        wo.write({"duration": 17.5})

        wo._sbk_record_duration_if_zero()

        self.assertEqual(wo.duration, 17.5,
                         "operator-entered duration must not be overwritten")

    # ──────────────────────────────────────────────────────────────────
    # 3. Idempotency
    # ──────────────────────────────────────────────────────────────────
    def test_button_finish_idempotent(self):
        asset = self._new_asset()
        _mo, wo, _req = self._new_mo_with_wo(
            op_qty_per_unit=2.0, qty_produced=10.0,
        )

        wo._sbk_debit_tool_lifecycle()
        wo._sbk_debit_tool_lifecycle()  # second call should be a no-op

        consumptions = self.Consumption.search([
            ("workorder_id", "=", wo.id),
        ])
        self.assertEqual(
            len(consumptions), 1,
            "Second call to _sbk_debit_tool_lifecycle must not re-debit "
            "thanks to the sbk_lifecycle_processed latch",
        )
        asset.invalidate_recordset()
        self.assertEqual(asset.remaining_life_qty, 80.0)
        self.assertEqual(asset.total_usage_qty, 20.0)

    def test_matching_operation_requirement_used_for_cloned_operation(self):
        asset = self._new_asset()
        _template_mo, template_wo, template_req = self._new_mo_with_wo(
            op_qty_per_unit=2.0, qty_produced=10.0,
        )
        _mo, wo, _empty_req = self._new_mo_with_wo(
            op_qty_per_unit=2.0, qty_produced=10.0, create_req=False,
        )
        self.assertNotEqual(template_wo.operation_id, wo.operation_id)
        self.assertFalse(self.OpReq.search([
            ("operation_id", "=", wo.operation_id.id),
        ]))

        wo._sbk_debit_tool_lifecycle()

        consumptions = self.Consumption.search([
            ("workorder_id", "=", wo.id),
        ])
        self.assertEqual(
            len(consumptions), 1,
            "Generated/cloned operations should reuse the matching "
            "source operation requirement instead of latching with no debit",
        )
        self.assertEqual(consumptions.asset_id, asset)
        self.assertEqual(consumptions.quantity, 20.0)
        self.assertEqual(template_req.workcenter_id, wo.workcenter_id)
        self.assertTrue(wo.sbk_lifecycle_processed)

    def test_no_resolved_consumption_leaves_lifecycle_unprocessed(self):
        _mo, wo, _empty_req = self._new_mo_with_wo(create_req=False)

        wo._sbk_debit_tool_lifecycle()

        consumptions = self.Consumption.search([
            ("workorder_id", "=", wo.id),
        ])
        self.assertFalse(consumptions)
        self.assertFalse(
            wo.sbk_lifecycle_processed,
            "No-debit runs must not close the lifecycle latch")

    # ──────────────────────────────────────────────────────────────────
    # 4. Sharpening activity raised at ≤10% remaining life
    # ──────────────────────────────────────────────────────────────────
    def test_low_life_raises_activity(self):
        # Pre-drain the asset to 15 / 100 (15%). With qty_per_unit=2.0
        # and qty_produced=10 the WO will debit 20 → 15-20 clamped to 0,
        # well below the 10% threshold.
        asset = self._new_asset(remaining_life_qty=15.0)
        _mo, wo, _req = self._new_mo_with_wo(
            op_qty_per_unit=2.0, qty_produced=10.0,
        )

        wo._sbk_debit_tool_lifecycle()

        activities = self.Activity.search([
            ("res_model", "=", "southbrook.tool.asset"),
            ("res_id", "=", asset.id),
            ("summary", "ilike", "Sharpening"),
        ])
        self.assertEqual(
            len(activities), 1,
            "Crossing the 10% threshold must schedule exactly one "
            "Sharpening / Replacement Due activity on the asset",
        )

        # And running the debit again (via a second WO on the same
        # asset) must not pile up duplicates while the original activity
        # is still open.
        _mo2, wo2, _req2 = self._new_mo_with_wo(
            op_qty_per_unit=0.0, qty_produced=1.0,
        )
        wo2._sbk_maybe_raise_sharpening_activity(asset)
        activities2 = self.Activity.search([
            ("res_model", "=", "southbrook.tool.asset"),
            ("res_id", "=", asset.id),
            ("summary", "ilike", "Sharpening"),
        ])
        self.assertEqual(len(activities2), 1,
                         "Open activity should be deduped on summary match")
