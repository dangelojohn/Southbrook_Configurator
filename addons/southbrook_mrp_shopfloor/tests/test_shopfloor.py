# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for CE-native shop-floor control.

The contract tests matter most: this module replaces one that the costing
layer and the finite-capacity scheduling engine both consume by name. A
missing attribute here surfaces as a TypeError deep inside a scheduling run,
not as a clear install failure.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_shopfloor")
class TestSouthbrookShopfloor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1)
        cls.wc = cls.env["mrp.workcenter"].create({
            "name": "TEST Bench", "costs_hour": 60.0,
        })
        cls.panel = cls.env["product.product"].create({
            "name": "TEST Panel", "type": "consu", "is_storable": True,
            "standard_price": 5.0,
        })
        cls.cabinet = cls.env["product.product"].create({
            "name": "TEST Cabinet", "type": "consu", "is_storable": False,
        })
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.cabinet.product_tmpl_id.id,
            "product_qty": 1.0, "type": "normal",
            "bom_line_ids": [(0, 0, {"product_id": cls.panel.id,
                                     "product_qty": 1.0})],
            "operation_ids": [
                (0, 0, {"name": "Cut", "workcenter_id": cls.wc.id,
                        "time_cycle_manual": 60.0, "sequence": 10}),
                (0, 0, {"name": "Assemble", "workcenter_id": cls.wc.id,
                        "time_cycle_manual": 60.0, "sequence": 20}),
            ],
        })

    def _mo(self, qty=1.0, confirm=True):
        mo = self.env["mrp.production"].create({
            "product_id": self.cabinet.id,
            "product_qty": qty,
            "product_uom_id": self.cabinet.uom_id.id,
            "bom_id": self.bom.id,
        })
        if confirm:
            mo.action_confirm()
        return mo

    # --- contract ----------------------------------------------------
    def test_sfc_capacity_signature_and_scalar_return(self):
        """_get_capacity returns a tuple in v19; this must return a number.

        The costing layer divides by this. A tuple leaking through would
        poison every cost silently rather than raising somewhere obvious.
        """
        with_product = self.wc._sfc_capacity(self.cabinet)
        without = self.wc._sfc_capacity()
        for value in (with_product, without):
            self.assertIsInstance(value, (int, float))
            self.assertGreater(value, 0.0)

    def test_contract_attributes_exist(self):
        """Names the costing module and scheduling engine consume."""
        wo_fields = self.env["mrp.workorder"]._fields
        for name in ("sfc_sequence", "date_planned_start_wo",
                     "date_planned_finished_wo", "date_actual_finished_wo",
                     "qty_output_wo"):
            self.assertIn(name, wo_fields, f"mrp.workorder.{name} is consumed "
                                           f"by another module")
        mo_fields = self.env["mrp.production"]._fields
        for name in ("date_planned_start_wo", "date_planned_finished_wo",
                     "is_scheduled"):
            self.assertIn(name, mo_fields)
        prod_fields = self.env["mrp.workcenter.productivity"]._fields
        for name in ("setup_duration", "working_duration",
                     "teardown_duration", "overall_duration"):
            self.assertIn(name, prod_fields)
        self.assertTrue(hasattr(self.env["mrp.workorder"],
                                "_rebuild_capacity_load"))

    # --- scheduling ---------------------------------------------------
    def test_scheduling_chains_operations_in_sequence(self):
        mo = self._mo()
        mo.schedule_workorders()
        wos = mo.workorder_ids.sorted(lambda w: w.sfc_sequence)
        self.assertEqual(len(wos), 2)
        self.assertTrue(all(w.date_planned_start_wo for w in wos))
        self.assertGreaterEqual(
            wos[1].date_planned_start_wo, wos[0].date_planned_finished_wo,
            "The second operation cannot start before the first finishes.")

    def test_scheduling_does_not_touch_native_dates(self):
        """Writing native date_start would create calendar leaves that
        double-book the workcenter against this very schedule."""
        mo = self._mo()
        before = mo.workorder_ids.mapped("date_start")
        mo.schedule_workorders()
        self.assertEqual(
            mo.workorder_ids.mapped("date_start"), before,
            "Native work-order dates must be left alone.")

    def test_capacity_load_rows_rebuilt(self):
        mo = self._mo()
        mo.schedule_workorders()
        rows = self.env["mrp.workcenter.load"].search(
            [("workorder_id", "in", mo.workorder_ids.ids)])
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r.week_nro for r in rows))
        # Rebuilding must replace, not accumulate.
        mo.workorder_ids._rebuild_capacity_load()
        rows = self.env["mrp.workcenter.load"].search(
            [("workorder_id", "in", mo.workorder_ids.ids)])
        self.assertEqual(len(rows), 2, "Rebuild must not duplicate rows.")

    # --- the completion gate -------------------------------------------
    def test_unscheduled_order_cannot_be_closed(self):
        """The gate that kept every MO in this database out of 'done'."""
        mo = self._mo()
        self.assertFalse(mo.is_scheduled)
        with self.assertRaises(UserError):
            mo.button_mark_done()

    def test_scheduled_order_passes_the_gate(self):
        mo = self._mo()
        mo.schedule_workorders()
        self.assertTrue(
            mo.is_scheduled,
            "Every operation is planned, so the order is schedulable-complete.")

    def test_is_scheduled_stays_true_once_work_is_done(self):
        """all() over every WO, not any() over the open ones.

        A finished work order carries no forward plan. An any()-style test
        would flip is_scheduled back to False after production, making the
        completion gate unreachable for exactly the orders that satisfied it.
        """
        mo = self._mo()
        mo.schedule_workorders()
        mo.workorder_ids.write({"date_planned_start_wo": False,
                                "state": "done"})
        mo.invalidate_recordset()
        self.assertTrue(
            mo.is_scheduled,
            "Done work orders satisfy the gate even without a forward date.")

    def test_order_without_operations_is_not_gated(self):
        """A BoM with no routing has nothing to schedule."""
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": self.panel.product_tmpl_id.id,
            "product_qty": 1.0, "type": "normal",
        })
        mo = self.env["mrp.production"].create({
            "product_id": self.panel.id, "product_qty": 1.0,
            "product_uom_id": self.panel.uom_id.id, "bom_id": bom.id,
        })
        mo.action_confirm()
        self.assertTrue(mo.is_scheduled)

    # --- floating times -------------------------------------------------
    def test_floating_times_autocreate(self):
        """The vendor raised UserError when the row was missing, turning a
        first scheduling attempt into a dead end."""
        self.env["mrp.floating.times"].search(
            [("warehouse_id", "=", self.warehouse.id)]).unlink()
        rec = self.env["mrp.floating.times"]._get_for_warehouse(self.warehouse)
        self.assertTrue(rec)
        self.assertEqual(rec.mrp_release_time, 1.0)
