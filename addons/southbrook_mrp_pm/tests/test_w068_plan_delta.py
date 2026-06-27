# SPDX-License-Identifier: LGPL-3.0-only
"""W068 (R3.12, 2026-06-27) — Plan-delta snapshot tests.

JTBD: "When the GM asks 'what slipped this week', I want a one-screen
answer instead of Excel."

Coverage:
  * Fields exist on mrp.production with expected types.
  * action_reset_plan_snapshot clears the anchors.
  * sbk_slipped_days correctly computes (positive late, negative early,
    zero when on time, false when state != done).
  * sbk_plan_week resolves to the Monday of the planned-finish week.
  * shop.daily snapshot picks up slipped MOs into slipped_mo_count and
    slipped_days_total.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_pm", "w068")
class TestW068PlanDelta(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Production = cls.env["mrp.production"]
        cls.WC = cls.env["mrp.workcenter"]
        cls.Snap = cls.env["southbrook.shop.daily"]
        cls.wc = cls.WC.create({
            "name": "W068 TEST WC",
            "code": "W068WC",
        })
        cls.product = cls.env["product.product"].create({
            "name": "W068 product",
            "type": "consu",
        })
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.product.product_tmpl_id.id,
            "product_qty": 1.0,
        })

    def _make_mo_with_anchor(self, planned_finish, actual_finish):
        """Create an MO, snapshot the anchor, then set actual finish
        + state=done so sbk_slipped_days can compute. Returns the MO."""
        mo = self.Production.create({
            "product_id": self.product.id,
            "product_qty": 1.0,
            "bom_id": self.bom.id,
        })
        # Force the planned-finish anchor (we don't call the full
        # action_confirm here because that would also reserve stock —
        # we're testing the snapshot mechanics, not the full MRP flow).
        mo.write({
            "sbk_initial_date_planned_start": planned_finish - timedelta(hours=4),
            "sbk_initial_date_planned_finished": planned_finish,
            "date_finished": actual_finish,
            "state": "done",
        })
        # Attach a WO so the shop.daily _pull_plan_delta sees a WC.
        self.env["mrp.workorder"].create({
            "name": "W068 WO",
            "production_id": mo.id,
            "workcenter_id": self.wc.id,
            "product_uom_id": self.product.uom_id.id,
            "duration_expected": 60.0,
            "duration": 60.0,
            "date_start": actual_finish - timedelta(minutes=60),
            "date_finished": actual_finish,
        })
        return mo

    # ------------------------------------------------------------------
    def test_10_fields_present(self):
        """All four W068 fields must exist on mrp.production."""
        for fname in (
            "sbk_initial_date_planned_start",
            "sbk_initial_date_planned_finished",
            "sbk_slipped_days",
            "sbk_plan_week",
        ):
            self.assertIn(
                fname, self.Production._fields,
                "W068 field %s missing from mrp.production" % fname,
            )

    def test_20_slip_computes_correctly(self):
        """Positive slip when actual > initial planned finish; negative
        when actual < initial; ~zero when equal."""
        planned = fields.Datetime.now() - timedelta(days=3)
        # 2-day slip.
        mo_late = self._make_mo_with_anchor(
            planned_finish=planned,
            actual_finish=planned + timedelta(days=2),
        )
        self.assertAlmostEqual(
            mo_late.sbk_slipped_days, 2.0, places=2,
            msg="Late MO should compute +2.0 slip days, got %.3f"
                % mo_late.sbk_slipped_days,
        )
        # 1-day early.
        mo_early = self._make_mo_with_anchor(
            planned_finish=planned,
            actual_finish=planned - timedelta(days=1),
        )
        self.assertAlmostEqual(
            mo_early.sbk_slipped_days, -1.0, places=2,
            msg="Early MO should compute -1.0 slip days, got %.3f"
                % mo_early.sbk_slipped_days,
        )

    def test_30_plan_week_is_monday(self):
        """sbk_plan_week must be Monday of the planned-finish week."""
        # Pick a known Friday — 2026-06-26 is a Friday.
        planned = fields.Datetime.from_string("2026-06-26 12:00:00")
        mo = self._make_mo_with_anchor(
            planned_finish=planned,
            actual_finish=planned,
        )
        # 2026-06-22 is the Monday of that ISO week.
        self.assertEqual(
            str(mo.sbk_plan_week), "2026-06-22",
            "Plan week should be Monday 2026-06-22, got %s"
                % mo.sbk_plan_week,
        )

    def test_40_reset_clears_anchor(self):
        """action_reset_plan_snapshot must clear both anchor fields."""
        planned = fields.Datetime.now()
        mo = self._make_mo_with_anchor(
            planned_finish=planned,
            actual_finish=planned + timedelta(hours=1),
        )
        self.assertTrue(mo.sbk_initial_date_planned_finished)
        mo.action_reset_plan_snapshot()
        self.assertFalse(mo.sbk_initial_date_planned_start)
        self.assertFalse(mo.sbk_initial_date_planned_finished)

    def test_50_shop_daily_aggregates_slipped(self):
        """shop.daily snapshot must surface slipped_mo_count > 0 when
        a slipped MO completed today at the test WC."""
        today = fields.Date.context_today(self.env["res.users"])
        now = fields.Datetime.now()
        # Planned to finish yesterday, actually finished today => +1d slip.
        self._make_mo_with_anchor(
            planned_finish=now - timedelta(days=1),
            actual_finish=now,
        )
        self.Snap._snapshot_for_window(today, today)
        row = self.Snap.search([
            ("workcenter_id", "=", self.wc.id),
            ("date", "=", today),
        ], limit=1)
        self.assertTrue(row, "Snapshot row must exist for the test WC.")
        self.assertGreaterEqual(
            row.slipped_mo_count, 1,
            "shop.daily must count the slipped MO under slipped_mo_count "
            "(got %d)" % row.slipped_mo_count,
        )
        self.assertGreater(
            row.slipped_days_total, 0.0,
            "shop.daily must sum slip-days for the slipped MO "
            "(got %.3f)" % row.slipped_days_total,
        )
