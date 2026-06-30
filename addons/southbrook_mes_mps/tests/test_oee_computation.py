# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestOeeComputation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.wc = self.env["mrp.workcenter"].create({
            "name": "MES OEE WC",
        })

    def test_oee_world_class(self):
        snap = self.env["southbrook.mes_mps.oee_snapshot"].create({
            "workcenter_id": self.wc.id,
            "shift_date": fields.Date.context_today(self.env["res.users"]),
            "shift": "morning",
            "planned_minutes": 480.0,
            "actual_run_minutes": 460.0,
            "actual_idle_minutes": 0.0,
            "actual_downtime_minutes": 20.0,
            "units_produced": 100,
            "units_target": 100,
            "units_rejected": 1,
        })
        # Availability = (480-20)/480 = 0.9583
        self.assertAlmostEqual(snap.availability, 460.0 / 480.0, places=4)
        # ideal_cycle = 480/100 = 4.8 ; perf = (100*4.8)/460 = 1.0434 → clamp 1.0
        self.assertAlmostEqual(snap.performance, 1.0, places=4)
        # quality = 99/100 = 0.99
        self.assertAlmostEqual(snap.quality, 0.99, places=4)
        expected_oee = (460.0 / 480.0) * 1.0 * 0.99
        self.assertAlmostEqual(snap.oee, expected_oee, places=4)
        # ≈ 0.9487 → world_class (>0.85)
        self.assertEqual(snap.oee_class, "world_class")

    def test_oee_unacceptable(self):
        snap = self.env["southbrook.mes_mps.oee_snapshot"].create({
            "workcenter_id": self.wc.id,
            "shift_date": fields.Date.context_today(self.env["res.users"]),
            "shift": "morning",
            "planned_minutes": 480.0,
            "actual_run_minutes": 200.0,
            "actual_idle_minutes": 0.0,
            "actual_downtime_minutes": 280.0,
            "units_produced": 50,
            "units_target": 200,
            "units_rejected": 10,
        })
        # Heavy downtime + low produce → oee should be terrible.
        self.assertLess(snap.oee, 0.4)
        self.assertEqual(snap.oee_class, "unacceptable")

    def test_oee_zero_division_safe(self):
        snap = self.env["southbrook.mes_mps.oee_snapshot"].create({
            "workcenter_id": self.wc.id,
            "shift_date": fields.Date.context_today(self.env["res.users"]),
            "shift": "morning",
            "planned_minutes": 0.0,
            "actual_run_minutes": 0.0,
            "actual_idle_minutes": 0.0,
            "actual_downtime_minutes": 0.0,
            "units_produced": 0,
            "units_target": 0,
            "units_rejected": 0,
        })
        self.assertEqual(snap.oee, 0.0)
