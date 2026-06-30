# SPDX-License-Identifier: LGPL-3.0-only
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestMpsRolling13Weeks(TransactionCase):
    def setUp(self):
        super().setUp()
        self.product = self.env["product.product"].create({
            "name": "MPS Test Cabinet",
            "type": "consu",
        })
        self.MPS = self.env["southbrook.mes_mps.mps_period"]

    def test_generate_creates_13_rows(self):
        rows = self.MPS.action_generate_rolling_13_weeks(self.product.id)
        self.assertEqual(
            len(rows), 13, "Rolling MPS must seed exactly 13 weeks."
        )
        # All distinct Mondays.
        starts = rows.mapped("week_start")
        self.assertEqual(len(set(starts)), 13)
        # First row is the Monday of the current ISO week.
        today = fields.Date.context_today(self.MPS)
        expected_start = today - timedelta(days=today.weekday())
        self.assertEqual(min(starts), expected_start)

    def test_generate_is_idempotent(self):
        first = self.MPS.action_generate_rolling_13_weeks(self.product.id)
        second = self.MPS.action_generate_rolling_13_weeks(self.product.id)
        # Second call must return the same set; no duplicates created.
        self.assertEqual(len(first), len(second))
        all_rows = self.MPS.search(
            [("product_id", "=", self.product.id)]
        )
        self.assertEqual(len(all_rows), 13)
