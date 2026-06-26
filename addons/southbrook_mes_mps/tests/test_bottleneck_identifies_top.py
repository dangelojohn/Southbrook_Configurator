# SPDX-License-Identifier: LGPL-3.0-only
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestBottleneckIdentifiesTop(TransactionCase):
    def setUp(self):
        super().setUp()
        self.WC = self.env["mrp.workcenter"]
        # Tag with active=False so the live action_compute() doesn't
        # sweep them in alongside other test fixtures.
        self.low = self.WC.create({"name": "BTLNCK LowWC"})
        self.med = self.WC.create({"name": "BTLNCK MedWC"})
        self.high = self.WC.create({"name": "BTLNCK HighWC"})
        today = fields.Date.context_today(self.env["res.users"])
        self.week_start = today - timedelta(days=today.weekday())
        Cap = self.env["southbrook.mes_mps.workcenter_capacity"]
        # Pre-seed capacity rows so action_compute() can read them.
        Cap.create({
            "workcenter_id": self.low.id,
            "week_start": self.week_start,
            "available_hours": 40.0,
            "planned_hours": 10.0,
        })
        Cap.create({
            "workcenter_id": self.med.id,
            "week_start": self.week_start,
            "available_hours": 40.0,
            "planned_hours": 30.0,
        })
        Cap.create({
            "workcenter_id": self.high.id,
            "week_start": self.week_start,
            "available_hours": 40.0,
            "planned_hours": 60.0,
        })

    def test_top_bottleneck_is_highest_load(self):
        report = self.env["southbrook.mes_mps.bottleneck_report"].create({
            "as_of_date": self.week_start,
        })
        report.action_compute()
        # Of the three seeded WCs, HighWC has the largest planned_hours
        # and therefore the largest load_pct. Restrict the assertion to
        # only the three WCs we created (other tests/data may have left
        # more workcenters around).
        relevant = report.line_ids.filtered(
            lambda l: l.workcenter_id in (self.low | self.med | self.high)
        )
        top = max(relevant, key=lambda l: l.load_pct)
        self.assertEqual(top.workcenter_id, self.high)
        self.assertGreater(top.load_pct, 100.0)
        self.assertEqual(top.recommended_action, "add_shift")
