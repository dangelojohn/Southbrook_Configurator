# SPDX-License-Identifier: LGPL-3.0-only
from datetime import datetime, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestWorkcenterLoad(TransactionCase):
    def setUp(self):
        super().setUp()
        self.wc = self.env["mrp.workcenter"].create({
            "name": "MES Test WC",
        })
        today = fields.Date.context_today(self.env["res.users"])
        self.week_start = today - timedelta(days=today.weekday())
        self.cap = self.env["southbrook.mes_mps.workcenter_capacity"].create({
            "workcenter_id": self.wc.id,
            "week_start": self.week_start,
            "available_hours": 40.0,
        })

    def test_load_pct_zero_when_no_workorders(self):
        self.cap._compute_planned_hours()
        self.assertEqual(self.cap.planned_hours, 0.0)
        self.assertEqual(self.cap.load_pct, 0.0)
        self.assertFalse(self.cap.is_overloaded)

    def test_load_pct_computes_from_workorders(self):
        # Stage a product + BOM + MO so we get a concrete workorder.
        product = self.env["product.product"].create({
            "name": "MES Load Test Product",
            "type": "consu",
        })
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
        })
        op = self.env["mrp.routing.workcenter"].create({
            "bom_id": bom.id,
            "name": "Op",
            "workcenter_id": self.wc.id,
            "time_cycle_manual": 120.0,
        })
        mo = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        # Force a workorder date inside the week.
        wo = self.env["mrp.workorder"].create({
            "name": "Test WO",
            "production_id": mo.id,
            "workcenter_id": self.wc.id,
            "product_uom_id": product.uom_id.id,
            "operation_id": op.id,
            "duration_expected": 120.0,
            "date_start": datetime.combine(
                self.week_start + timedelta(days=1),
                datetime.min.time().replace(hour=9),
            ),
            "state": "ready",
        })
        # Trigger compute.
        self.cap.invalidate_recordset(["planned_hours", "load_pct"])
        self.cap._compute_planned_hours()
        self.cap._compute_load()
        # 120 min == 2 hours; 2 / 40 = 5%.
        self.assertAlmostEqual(self.cap.planned_hours, 2.0, places=2)
        self.assertAlmostEqual(self.cap.load_pct, 5.0, places=2)
        self.assertFalse(self.cap.is_overloaded)
        del wo  # silence unused
