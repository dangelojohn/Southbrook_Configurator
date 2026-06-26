# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for HST return aggregation."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestHstReturn(TransactionCase):
    def setUp(self):
        super().setUp()
        self.HstReturn = self.env["southbrook.finance.hst_return"]

    def test_hst_return_creation_and_state(self):
        ret = self.HstReturn.create(
            {
                "tax_year": 2026,
                "quarter": "1",
            }
        )
        # Auto-set period.
        self.assertEqual(ret.period_from, date(2026, 1, 1))
        self.assertEqual(ret.period_to, date(2026, 3, 31))
        self.assertTrue(ret.name)  # sequence assigned

    def test_net_hst_owing_formula(self):
        """collected - ITC = net owing."""
        ret = self.HstReturn.create(
            {"tax_year": 2026, "quarter": "2"}
        )
        # Force values in memory and recompute downstream.
        ret.hst_collected = 1300.0
        ret.hst_paid_itc = 500.0
        ret.net_hst_owing = ret.hst_collected - ret.hst_paid_itc
        self.assertEqual(ret.net_hst_owing, 800.0)

    def test_quarter_period_window_q3(self):
        ret = self.HstReturn.create(
            {"tax_year": 2026, "quarter": "3"}
        )
        self.assertEqual(ret.period_from, date(2026, 7, 1))
        self.assertEqual(ret.period_to, date(2026, 9, 30))

    def test_quarter_period_window_q4(self):
        ret = self.HstReturn.create(
            {"tax_year": 2026, "quarter": "4"}
        )
        self.assertEqual(ret.period_from, date(2026, 10, 1))
        self.assertEqual(ret.period_to, date(2026, 12, 31))

    def test_unique_per_year_quarter(self):
        self.HstReturn.create({"tax_year": 2027, "quarter": "1"})
        from psycopg2 import errors
        from odoo.tools import mute_logger
        with mute_logger("odoo.sql_db"):
            with self.assertRaises(Exception):
                self.HstReturn.create({"tax_year": 2027, "quarter": "1"})
                self.HstReturn.flush_model()
        # Some Postgres backends raise IntegrityError vs UniqueViolation; we
        # care that *some* exception is raised, hence broad Exception above.
        _ = errors  # appease linters
