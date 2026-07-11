# SPDX-License-Identifier: LGPL-3.0-only
"""Shadow scheduling engine tests (§6).

Uses the main company (which owns a manufacturing warehouse so MOs can confirm)
and scopes every assertion to the MOs the test itself creates, so it is robust to
any pre-existing data. BoMs omit components so no stock reservation is needed.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "oiq")
class TestShadowScheduler(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.svc = cls.env["oiq.scheduling.intelligence"]
        cls.calendar = cls.env["resource.calendar"].create({
            "name": "OIQ Shadow Cal", "company_id": False})

    def _wc(self, name):
        return self.env["mrp.workcenter"].create({
            "name": name, "company_id": False,
            "resource_calendar_id": self.calendar.id, "time_efficiency": 100.0})

    def _confirmed_mo(self, name, operations, deadline=None):
        """operations = list of (workcenter, minutes)."""
        product = self.env["product.product"].create({"name": name, "type": "consu"})
        op_vals = [(0, 0, {
            "name": f"Op{i}", "workcenter_id": wc.id,
            "time_cycle_manual": mins, "time_mode": "manual",
        }) for i, (wc, mins) in enumerate(operations)]
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0, "type": "normal", "operation_ids": op_vals,
        })
        mo_vals = {"product_id": product.id, "product_qty": 1.0,
                   "bom_id": bom.id, "company_id": self.company.id}
        if deadline:
            mo_vals["date_deadline"] = deadline
        mo = self.env["mrp.production"].create(mo_vals)
        mo.action_confirm()
        return mo

    def _slots_for(self, run, mo):
        return run.slot_ids.filtered(lambda s: s.production_id == mo).sorted("seq")

    # ----------------------------------------------------------------- tests
    def test_shadow_schedule_creates_run_and_slots(self):
        wc = self._wc("CNC")
        mo = self._confirmed_mo("Cab A", [(wc, 60.0)])
        self.assertTrue(mo.workorder_ids, "MO should have work orders after confirm")

        run = self.svc.shadow_schedule(self.company, 14)
        self.assertEqual(run.state, "complete")
        slots = self._slots_for(run, mo)
        self.assertEqual(len(slots), len(mo.workorder_ids))
        self.assertGreater(slots[0].planned_finish, slots[0].planned_start)
        self.assertTrue(slots[0].predicted_complete)

    def test_shadow_never_writes_to_mrp(self):
        wc = self._wc("CNC")
        mo = self._confirmed_mo("Cab B", [(wc, 45.0)])
        wos = mo.workorder_ids
        before = {w.id: (w.date_start, w.date_finished, w.write_date) for w in wos}

        self.svc.shadow_schedule(self.company, 14)

        after = {w.id: (w.date_start, w.date_finished, w.write_date)
                 for w in self.env["mrp.workorder"].browse(list(before))}
        self.assertEqual(before, after, "shadow schedule must not mutate mrp.workorder")

    def test_flow_shop_precedence_holds(self):
        wc1, wc2 = self._wc("Cut"), self._wc("Assemble")
        mo = self._confirmed_mo("Cab C", [(wc1, 60.0), (wc2, 30.0)])
        self.assertEqual(len(mo.workorder_ids), 2)

        run = self.svc.shadow_schedule(self.company, 14)
        slots = self._slots_for(run, mo)
        self.assertEqual(len(slots), 2)
        # op2 cannot start before op1 finishes (different work centers → pure precedence)
        self.assertGreaterEqual(slots[1].planned_start, slots[0].planned_finish)

    def test_edd_orders_earlier_deadline_first(self):
        wc = self._wc("Shared CNC")
        now = fields.Datetime.now()
        mo_late = self._confirmed_mo("Late Cab", [(wc, 60.0)], deadline=now + timedelta(days=10))
        mo_urgent = self._confirmed_mo("Urgent Cab", [(wc, 60.0)], deadline=now + timedelta(days=2))

        run = self.svc.shadow_schedule(self.company, 30)
        mine = (self._slots_for(run, mo_late) + self._slots_for(run, mo_urgent)).sorted("planned_start")
        # single work center, urgent deadline first
        self.assertEqual(mine[0].production_id, mo_urgent)
        # single-lane contention: the later slot starts no earlier than the first finishes
        self.assertGreaterEqual(mine[1].planned_start, mine[0].planned_finish)

    def test_vs_odoo_delta_computed_when_odoo_has_a_plan(self):
        wc = self._wc("CNC")
        mo = self._confirmed_mo("Cab D", [(wc, 60.0)])
        # Simulate Odoo having planned this WO in the past (test setup, not the engine).
        mo.workorder_ids[0].date_start = fields.Datetime.now() - timedelta(days=3)

        run = self.svc.shadow_schedule(self.company, 14)
        slot = self._slots_for(run, mo)[0]
        self.assertGreater(slot.vs_odoo_delta_min, 0.0)

    def test_backfill_actuals_fills_delta_on_completion(self):
        wc = self._wc("CNC")
        mo = self._confirmed_mo("Cab E", [(wc, 60.0)])
        run = self.svc.shadow_schedule(self.company, 14)
        slot = self._slots_for(run, mo)[0]
        self.assertFalse(slot.vs_actual_delta_min)

        wo = slot.workorder_id
        wo.write({"state": "done",
                  "date_finished": slot.predicted_complete + timedelta(minutes=60)})
        self.svc.backfill_actuals(self.company)

        self.assertAlmostEqual(slot.vs_actual_delta_min, 60.0, delta=1.0)
