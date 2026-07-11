# SPDX-License-Identifier: LGPL-3.0-only
"""Delivery-confidence tests (§8.A).

Confirms the estimate is always a RANGE (never a point), honest and wide for a
cold tenant, unique per MO, and that the quality-label thresholds hold.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "oiq")
class TestDelivery(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.svc = cls.env["oiq.scheduling.intelligence"]
        cls.calendar = cls.env["resource.calendar"].create({
            "name": "OIQ Delivery Cal", "company_id": False})

    def _wc(self, name):
        return self.env["mrp.workcenter"].create({
            "name": name, "company_id": False,
            "resource_calendar_id": self.calendar.id, "time_efficiency": 100.0})

    def _confirmed_mo(self, name, wc, minutes=60.0):
        product = self.env["product.product"].create({"name": name, "type": "consu"})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0, "type": "normal",
            "operation_ids": [(0, 0, {"name": "Cut", "workcenter_id": wc.id,
                                      "time_cycle_manual": minutes, "time_mode": "manual"})]})
        mo = self.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0,
            "bom_id": bom.id, "company_id": self.company.id})
        mo.action_confirm()
        return mo

    # ----------------------------------------------------------------- tests
    def test_estimate_is_a_range_never_a_point(self):
        mo = self._confirmed_mo("Cab A", self._wc("CNC"))
        est = self.svc.estimate_delivery(mo)
        self.assertEqual(est.production_id, mo)
        self.assertGreater(est.completion_end, est.completion_start)
        self.assertIn(est.prediction_quality, ("low", "med", "high"))
        self.assertTrue(est.basis_text)

    def test_cold_tenant_is_low_quality_and_wide(self):
        mo = self._confirmed_mo("Cab B", self._wc("CNC"))
        est = self.svc.estimate_delivery(mo)
        # No calibration history + no Level-4 audit → forced low, wide floor.
        self.assertEqual(est.prediction_quality, "low")
        width_days = (est.completion_end - est.completion_start).total_seconds() / 86400.0
        self.assertGreaterEqual(width_days, 0.9)  # at least the ~1-day floor

    def test_estimate_is_unique_per_mo(self):
        mo = self._confirmed_mo("Cab C", self._wc("CNC"))
        self.svc.estimate_delivery(mo)
        self.svc.estimate_delivery(mo)  # refresh, not duplicate
        count = self.env["oiq.delivery.estimate"].search_count(
            [("production_id", "=", mo.id)])
        self.assertEqual(count, 1)

    def test_quality_label_thresholds(self):
        q = self.svc._quality_label
        self.assertEqual(q(10, None, 2), "low")     # thin data, low readiness
        self.assertEqual(q(25, 50.0, 4), "med")     # calibrated but modest accuracy
        self.assertEqual(q(120, 85.0, 4), "high")   # lots of samples + accurate
        self.assertEqual(q(120, 85.0, 3), "low")    # readiness < 4 vetoes everything

    def test_backtest_none_without_completed_history(self):
        pct, window = self.svc._backtest_accuracy(self.company, "any-cohort")
        self.assertIsNone(pct)
        self.assertEqual(window, 3)
