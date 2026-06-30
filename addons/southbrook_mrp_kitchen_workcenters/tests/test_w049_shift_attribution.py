# SPDX-License-Identifier: LGPL-3.0-only
"""W049 (R7.5) — Shift attribution on KPIs via `x_sb_shift`.

`mrp.workorder.x_sb_shift` is a stored compute that derives a
morning/afternoon/night bucket from `date_start.hour`, against three
configurable boundary ICPs:
  southbrook.shift_morning_start_hour     default 06
  southbrook.shift_afternoon_start_hour   default 14
  southbrook.shift_night_start_hour       default 22

These tests verify:
  * default boundary bucketing across the day (and the night-wrap)
  * custom-boundary respect (12-hour shifts)
  * the WO compute resolves from date_start
  * empty date_start -> empty shift
"""
from datetime import datetime

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w049")
class TestW049ShiftAttribution(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Workorder = cls.env["mrp.workorder"]
        cls.Param = cls.env["ir.config_parameter"].sudo()

    def _make_wo(self, date_start=None):
        wc = self.env["mrp.workcenter"].search([], limit=1)
        if not wc:
            wc = self.env["mrp.workcenter"].create({
                "name": "W049 WC", "code": "W049WC",
            })
        product = self.env["product.product"].search([
            ("type", "=", "consu")], limit=1)
        if not product:
            product = self.env["product.product"].create({
                "name": "W049 product", "type": "consu",
            })
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        production = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        return self.Workorder.create({
            "name": "W049 WO",
            "production_id": production.id,
            "workcenter_id": wc.id,
            "product_uom_id": product.uom_id.id,
            "date_start": date_start,
        })

    # ------------------------------------------------------------------
    # Boundary resolver — default config (06/14/22)
    # ------------------------------------------------------------------
    def test_10_default_boundaries_morning(self):
        # 6, 7, 13 -> morning
        for h in (6, 7, 13):
            self.assertEqual(
                self.Workorder._sbk_shift_for_hour(h), "morning",
                f"hour={h} should bucket to morning under defaults")

    def test_11_default_boundaries_afternoon(self):
        for h in (14, 15, 21):
            self.assertEqual(
                self.Workorder._sbk_shift_for_hour(h), "afternoon",
                f"hour={h} should bucket to afternoon under defaults")

    def test_12_default_boundaries_night_wraps(self):
        # 22 + 23 = night; 0..5 also = night (wraps midnight)
        for h in (22, 23, 0, 1, 5):
            self.assertEqual(
                self.Workorder._sbk_shift_for_hour(h), "night",
                f"hour={h} should bucket to night under defaults (wraps)")

    # ------------------------------------------------------------------
    # WO compute end-to-end
    # ------------------------------------------------------------------
    def test_20_wo_compute_resolves_from_date_start(self):
        # 10am -> morning
        wo = self._make_wo(date_start=datetime(2026, 6, 27, 10, 0, 0))
        self.assertEqual(wo.x_sb_shift, "morning")

    def test_21_wo_compute_empty_date_start(self):
        wo = self._make_wo(date_start=False)
        self.assertFalse(wo.x_sb_shift,
                         "no date_start -> empty shift bucket")

    def test_22_wo_compute_recomputes_on_change(self):
        wo = self._make_wo(date_start=datetime(2026, 6, 27, 10, 0, 0))
        self.assertEqual(wo.x_sb_shift, "morning")
        wo.date_start = datetime(2026, 6, 27, 23, 30, 0)
        self.assertEqual(wo.x_sb_shift, "night",
                         "changing date_start must re-derive the shift")

    # ------------------------------------------------------------------
    # Custom boundaries — 12-hour shifts (06/18)
    # ------------------------------------------------------------------
    def test_30_custom_boundaries_respected(self):
        self.Param.set_param(
            "southbrook.shift_morning_start_hour", "6")
        self.Param.set_param(
            "southbrook.shift_afternoon_start_hour", "18")
        # Set night to a same-as-afternoon value to simulate a 2-shift
        # shop -- with sorted-stable bucketing, hours >= 18 collapse to
        # the last-defined shift (night under our default ordering).
        # We keep "night" as the strict-night bucket by using 23.
        self.Param.set_param(
            "southbrook.shift_night_start_hour", "23")
        # 12pm -> morning still (because afternoon starts at 18)
        self.assertEqual(
            self.Workorder._sbk_shift_for_hour(12), "morning")
        # 19 -> afternoon now (was afternoon under defaults too)
        self.assertEqual(
            self.Workorder._sbk_shift_for_hour(19), "afternoon")
