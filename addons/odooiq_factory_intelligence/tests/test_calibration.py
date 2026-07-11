# SPDX-License-Identifier: LGPL-3.0-only
"""Calibration engine tests (§7) — the Factory Learning Graph.

Observations are captured directly from work orders the test creates (not via the
harvest sweep) so results are deterministic regardless of any pre-existing done
work orders in the shared DB.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "oiq")
class TestCalibration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.svc = cls.env["oiq.scheduling.intelligence"]
        cls.calendar = cls.env["resource.calendar"].create({
            "name": "OIQ Calib Cal", "company_id": False})
        cls.Obs = cls.env["oiq.completion.observation"]
        cls.Factor = cls.env["oiq.calibration.factor"]

    def _wc(self, name):
        return self.env["mrp.workcenter"].create({
            "name": name, "company_id": False,
            "resource_calendar_id": self.calendar.id, "time_efficiency": 100.0})

    def _confirmed_mo(self, name, wc, n_ops):
        product = self.env["product.product"].create({"name": name, "type": "consu"})
        ops = [(0, 0, {"name": "Paint", "workcenter_id": wc.id,
                       "time_cycle_manual": 30.0, "time_mode": "manual"})
               for _ in range(n_ops)]
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0, "type": "normal", "operation_ids": ops})
        mo = self.env["mrp.production"].create({
            "product_id": product.id, "product_qty": 1.0,
            "bom_id": bom.id, "company_id": self.company.id})
        mo.action_confirm()
        return mo

    def _finish_all(self, mo, ratio):
        """Give every WO an actual duration = ratio × its estimated duration.
        `duration` (actual minutes) is stored-and-writable; setting it directly
        avoids Odoo overriding date_start/finished on the done-state transition."""
        for wo in mo.workorder_ids:
            wo.duration = ratio * wo.duration_expected

    def _capture(self, mo):
        for wo in mo.workorder_ids:
            self.svc._capture_observation(wo)

    def _paint_factor(self):
        return self.Factor.search([
            ("company_id", "=", self.company.id),
            ("scope", "=", "operation_category"), ("key", "=", "paint")])

    # ----------------------------------------------------------------- tests
    def test_capture_records_ratio_and_category(self):
        wc = self._wc("Booth")
        mo = self._confirmed_mo("Cab A", wc, 1)
        self._finish_all(mo, 2.0)
        self._capture(mo)

        obs = self.Obs.search([("workorder_id", "in", mo.workorder_ids.ids)])
        self.assertEqual(len(obs), 1)
        self.assertAlmostEqual(obs.ratio, 2.0, delta=0.05)
        self.assertEqual(obs.operation_category, "paint")

    def test_capture_is_idempotent(self):
        wc = self._wc("Booth")
        mo = self._confirmed_mo("Cab B", wc, 1)
        self._finish_all(mo, 1.5)
        self._capture(mo)
        self._capture(mo)  # second pass must not duplicate
        obs = self.Obs.search([("workorder_id", "in", mo.workorder_ids.ids)])
        self.assertEqual(len(obs), 1)

    def test_recompute_creates_operation_category_factor(self):
        wc = self._wc("Booth")
        mo = self._confirmed_mo("Cab C", wc, 6)
        self._finish_all(mo, 2.0)
        self._capture(mo)
        obs_count = self.Obs.search_count([("workorder_id", "in", mo.workorder_ids.ids)])
        self.assertEqual(obs_count, 6, "all 6 WOs should be observed")

        self.svc.recompute_calibration(self.company)
        f = self._paint_factor()
        self.assertTrue(f, "an operation_category='paint' factor should exist")
        self.assertEqual(f.sample_count, 6)
        # blended toward 1.0 at low sample count (6 of 20)
        self.assertGreater(f.multiplier, 1.0)
        self.assertLess(f.multiplier, 2.0)
        self.assertGreater(f.confidence, 0.0)
        self.assertLessEqual(f.confidence, 1.0)

    def test_small_sample_emits_no_factor(self):
        wc = self._wc("Booth")
        mo = self._confirmed_mo("Cab D", wc, 3)  # below MIN_SAMPLE_THRESHOLD (5)
        self._finish_all(mo, 2.0)
        self._capture(mo)
        self.svc.recompute_calibration(self.company)
        self.assertFalse(self._paint_factor(), "no factor below the sample threshold")

    def test_calibration_feeds_the_scheduler(self):
        """The moat: a learned 2.0x factor corrects a future WO's projected
        duration to ~2x its raw estimate."""
        wc = self._wc("Booth")
        mo = self._confirmed_mo("Cab E", wc, 20)  # full-trust sample size
        self._finish_all(mo, 2.0)
        self._capture(mo)
        self.svc.recompute_calibration(self.company)
        f = self._paint_factor()
        self.assertAlmostEqual(f.multiplier, 2.0, delta=0.1)  # full trust ≈ raw median

        # A brand-new (not-yet-done) Paint work order picks up the correction.
        mo2 = self._confirmed_mo("Cab F", wc, 1)
        wo2 = mo2.workorder_ids[0]
        cal_map = self.svc._load_calibration_factors(self.company)
        cal_min, conf = self.svc._calibrated_duration(wo2, cal_map)
        self.assertAlmostEqual(cal_min, wo2.duration_expected * 2.0,
                               delta=wo2.duration_expected * 0.1)
        self.assertGreater(conf, 0.0)
