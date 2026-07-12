# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for CCA depreciation schedule generation.

The CRA Class-8 declining-balance series on a $10,000 acquisition with the
half-year rule (no AII) is the textbook reference:

    Yr 1: 10,000 * 0.20 * 0.5 = 1,000      (closing 9,000)
    Yr 2: 9,000  * 0.20       = 1,800      (closing 7,200)
    Yr 3: 7,200  * 0.20       = 1,440      (closing 5,760)
    Yr 4: 5,760  * 0.20       = 1,152      (closing 4,608)
    Yr 5: 4,608  * 0.20       =   921.60   (closing 3,686.40)

With the Accelerated Investment Incentive ON, year 1 becomes 3x the
half-year baseline (1.5 x normal rate against full cost) -- $3,000 on a
$10,000 Class-8 acquisition.
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestCcaSchedule(TransactionCase):
    def setUp(self):
        super().setUp()
        self.CcaClass = self.env["southbrook.finance.cca_class"]
        self.Asset = self.env["southbrook.finance.asset"]
        # Class 8 -- declining balance 20%, half-year rule ON, AII OFF for
        # the textbook test.
        self.class_8 = self.CcaClass.create(
            {
                "name": "Test Class 8",
                "code": "TEST-CCA-8",
                "rate_pct": 20.0,
                "half_year_rule": True,
                "accelerated_investment_incentive": False,
            }
        )
        # Class 8 with AII for the AII test.
        self.class_8_aii = self.CcaClass.create(
            {
                "name": "Test Class 8 AII",
                "code": "TEST-CCA-8-AII",
                "rate_pct": 20.0,
                "half_year_rule": True,
                "accelerated_investment_incentive": True,
            }
        )
        # Class 29 -- straight-line 3 years.
        self.class_29 = self.CcaClass.create(
            {
                "name": "Test Class 29",
                "code": "TEST-CCA-29",
                "rate_pct": 50.0,
                "half_year_rule": False,
                "accelerated_investment_incentive": False,
                "straight_line": True,
                "straight_line_years": 3,
            }
        )

    def _new_asset(self, cca_class, cost=10000.0):
        return self.Asset.create(
            {
                "name": "Test Asset for %s" % cca_class.code,
                "cca_class_id": cca_class.id,
                "acquisition_date": "2026-01-01",
                "acquisition_cost": cost,
            }
        )

    def test_cca_class_8_full_schedule(self):
        """$10,000 Class 8, half-year, no AII -- textbook 5-year series."""
        asset = self._new_asset(self.class_8, 10000.0)
        rows = asset.compute_schedule_rows(years=5)
        amounts = [round(r["cca_amount"], 2) for r in rows]
        closings = [round(r["closing_balance"], 2) for r in rows]
        self.assertEqual(amounts, [1000.0, 1800.0, 1440.0, 1152.0, 921.60])
        self.assertEqual(closings, [9000.0, 7200.0, 5760.0, 4608.0, 3686.40])

    def test_class_29_straight_line(self):
        """Class 29 = 50% straight-line over 3 years on $10,000."""
        asset = self._new_asset(self.class_29, 10000.0)
        rows = asset.compute_schedule_rows(years=4)
        amounts = [round(r["cca_amount"], 2) for r in rows]
        # 10,000 / 3 = 3,333.33 per year for 3 years, then 0.
        self.assertAlmostEqual(amounts[0], 3333.33, places=2)
        self.assertAlmostEqual(amounts[1], 3333.33, places=2)
        # Final slice clamps to whatever's left to avoid float drift below 0.
        self.assertAlmostEqual(sum(amounts[:3]), 10000.0, places=2)
        self.assertEqual(amounts[3], 0.0)

    def test_aii_first_year(self):
        """AII year-1 = 3 x the half-year baseline rate.

        On $10,000 Class 8 the half-year baseline is $1,000; AII pushes it
        to $3,000 (= 1.5 x 20% full rate, equivalent to 3x the half-rate).
        """
        asset = self._new_asset(self.class_8_aii, 10000.0)
        rows = asset.compute_schedule_rows(years=2)
        self.assertAlmostEqual(rows[0]["cca_amount"], 3000.0, places=2)
        # Year 2 then uses straight declining-balance off the new opening
        # balance: 7,000 * 0.20 = 1,400.
        self.assertAlmostEqual(rows[1]["cca_amount"], 1400.0, places=2)

    def test_action_generate_schedule_persists_rows(self):
        """The ORM action should write schedule lines."""
        asset = self._new_asset(self.class_8, 10000.0)
        asset.action_generate_schedule(years=5)
        self.assertEqual(len(asset.schedule_ids), 5)
        # Accumulated depreciation counts only POSTED (taken) lines, not the
        # whole projected schedule. Freshly generated => nothing posted =>
        # accumulated 0.0 and net_book_value still the full acquisition cost.
        self.assertAlmostEqual(asset.accumulated_depreciation, 0.0, places=2)
        self.assertAlmostEqual(asset.net_book_value, 10000.0, places=2)
        # Post the first two years and re-check: accumulated tracks the posted
        # slice, NBV falls by exactly that much.
        posted = asset.schedule_ids.sorted("year")[:2]
        posted.write({"posted": True})
        expected_acc = sum(posted.mapped("cca_amount"))
        self.assertAlmostEqual(
            asset.accumulated_depreciation, expected_acc, places=2)
        self.assertAlmostEqual(
            asset.net_book_value, 10000.0 - expected_acc, places=2)

    def test_cannot_regenerate_if_posted(self):
        asset = self._new_asset(self.class_8, 10000.0)
        asset.action_generate_schedule(years=3)
        asset.schedule_ids[0].posted = True
        with self.assertRaises(UserError):
            asset.action_generate_schedule(years=3)
