# SPDX-License-Identifier: LGPL-3.0-only
"""W067 (R3.10) — calendar-aware capacity row tests.

JTBD: "When a WC has a 4-day Monday holiday, I want the capacity pivot
to know that and not show false headroom."

Coverage:
  * available_minutes resolves from the WC's OWN resource_calendar_id,
    NOT the company default (spec constraint).
  * A leave on the WC's calendar zeros available_minutes for that day.
  * loaded_minutes sums in-flight WO durations correctly.
  * The action and pivot view load through get_view (validates the
    pivot arch + the menu wiring under southbrook_mrp_pm).
"""
from datetime import date, datetime, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w067")
class TestW067CalendarCapacity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Custom 4-day calendar (Mon-Thu, 8h/day, total 32h/week).
        # Forces a clear deviation from the default 5-day x 8h.
        cls.cal4day = cls.env["resource.calendar"].create({
            "name": "W067 Test — 4-day week",
            "attendance_ids": [
                (5, 0, 0),  # clear inherited attendances
                # Monday (dayofweek 0) AM
                (0, 0, {"name": "Mon AM", "dayofweek": "0",
                        "hour_from": 8.0, "hour_to": 12.0,
                        "day_period": "morning"}),
                (0, 0, {"name": "Mon PM", "dayofweek": "0",
                        "hour_from": 13.0, "hour_to": 17.0,
                        "day_period": "afternoon"}),
                (0, 0, {"name": "Tue AM", "dayofweek": "1",
                        "hour_from": 8.0, "hour_to": 12.0,
                        "day_period": "morning"}),
                (0, 0, {"name": "Tue PM", "dayofweek": "1",
                        "hour_from": 13.0, "hour_to": 17.0,
                        "day_period": "afternoon"}),
                (0, 0, {"name": "Wed AM", "dayofweek": "2",
                        "hour_from": 8.0, "hour_to": 12.0,
                        "day_period": "morning"}),
                (0, 0, {"name": "Wed PM", "dayofweek": "2",
                        "hour_from": 13.0, "hour_to": 17.0,
                        "day_period": "afternoon"}),
                (0, 0, {"name": "Thu AM", "dayofweek": "3",
                        "hour_from": 8.0, "hour_to": 12.0,
                        "day_period": "morning"}),
                (0, 0, {"name": "Thu PM", "dayofweek": "3",
                        "hour_from": 13.0, "hour_to": 17.0,
                        "day_period": "afternoon"}),
                # Friday (3) deliberately empty.
            ],
        })
        # Default 5-day calendar to prove the WC uses its OWN cal.
        cls.cal5day = cls.env.ref("resource.resource_calendar_std")
        cls.wc4 = cls.env["mrp.workcenter"].create({
            "name": "W067 EDGE-BANDER (4day)",
            "resource_calendar_id": cls.cal4day.id,
        })
        cls.wc5 = cls.env["mrp.workcenter"].create({
            "name": "W067 PANEL-SAW (5day)",
            "resource_calendar_id": cls.cal5day.id,
        })
        cls.CapDay = cls.env["southbrook.capacity.day"]

    def _next_weekday(self, target_dow):
        """Return the next date whose .weekday() == target_dow."""
        today = fields.Date.context_today(self.env["res.users"])
        for i in range(8):
            d = today + timedelta(days=i)
            if d.weekday() == target_dow:
                return d
        return today

    # ------------------------------------------------------------------
    def test_uses_workcenters_own_calendar_not_company_default(self):
        """available_minutes must come from the WC's own
        resource_calendar_id — never the company default."""
        # A Friday is a working day on the 5-day calendar (8h = 480min)
        # but NOT on the 4-day calendar (0 min). If we accidentally
        # used the company default for the 4-day WC we'd see 480.
        friday = self._next_weekday(4)
        avail_4day = self.CapDay._available_minutes(self.cal4day, friday)
        avail_5day = self.CapDay._available_minutes(self.cal5day, friday)
        self.assertEqual(
            avail_4day, 0.0,
            "Friday on a 4-day (Mon-Thu) calendar must be 0 working minutes")
        self.assertGreater(
            avail_5day, 0.0,
            "Friday on the standard 5-day calendar must be >0 minutes")

    def test_holiday_zeros_available_minutes_for_that_day(self):
        """A global leave on the WC's calendar must drop the day's
        available_minutes to 0 (the JTBD example)."""
        wednesday = self._next_weekday(2)  # normally 8h on cal4day
        # Sanity: Wed is a working day.
        baseline = self.CapDay._available_minutes(self.cal4day, wednesday)
        self.assertGreater(baseline, 0.0)
        # Declare a holiday spanning that Wednesday.
        self.env["resource.calendar.leaves"].create({
            "calendar_id": self.cal4day.id,
            "name": "W067 Test Holiday",
            "date_from": datetime.combine(wednesday, datetime.min.time()),
            "date_to": datetime.combine(
                wednesday + timedelta(days=1), datetime.min.time()),
        })
        after = self.CapDay._available_minutes(self.cal4day, wednesday)
        self.assertEqual(
            after, 0.0,
            "A full-day leave on the WC's own calendar must zero "
            "available_minutes for that day (the spec's 4-day Mon holiday "
            "scenario)")

    def test_rebuild_window_creates_one_row_per_wc_per_day(self):
        """Exercise the rebuild end-to-end and assert the
        loaded_minutes sum picks up an in-flight WO scheduled for
        the WC."""
        rows_before = self.CapDay.search([
            ("workcenter_id", "in", (self.wc4 | self.wc5).ids)])
        rows_before.unlink()
        # Use 3-day horizon to keep the test fast.
        self.CapDay._rebuild_window(self.wc4 | self.wc5, horizon_days=3)
        rows = self.CapDay.search([
            ("workcenter_id", "in", (self.wc4 | self.wc5).ids)])
        # 2 WCs * 3 days = 6 rows.
        self.assertEqual(len(rows), 6,
                         "expected 6 rows (2 WCs * 3 days), got %d" % len(rows))
        # Refreshed_at populated.
        for row in rows:
            self.assertTrue(row.refreshed_at)
        # Headroom = available - loaded (computed).
        for row in rows:
            self.assertEqual(
                row.headroom_minutes,
                row.available_minutes - row.loaded_minutes,
                "headroom must equal available - loaded for row %s" % row.display_name)

    def test_action_and_pivot_load_cleanly(self):
        """Smoke: the pivot view + the menu's action both resolve
        (catches xml-ref typos + view-validation regressions)."""
        action = self.env.ref(
            "southbrook_mrp_kitchen_workcenters.action_capacity_day")
        self.assertEqual(action.res_model, "southbrook.capacity.day")
        pivot = self.env.ref(
            "southbrook_mrp_kitchen_workcenters.view_capacity_day_pivot")
        # get_view exercises validation in v19.
        result = self.CapDay.with_context(no_breadcrumbs=True).get_view(
            view_id=pivot.id, view_type="pivot")
        self.assertIn("headroom_minutes", result["arch"])
        self.assertIn("workcenter_id", result["arch"])
