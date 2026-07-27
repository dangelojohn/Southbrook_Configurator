# SPDX-License-Identifier: LGPL-3.0-only
from datetime import datetime, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestBottleneckIdentifiesTop(TransactionCase):
    def setUp(self):
        super().setUp()
        self.WC = self.env["mrp.workcenter"]
        self.low = self.WC.create({"name": "BTLNCK LowWC"})
        self.med = self.WC.create({"name": "BTLNCK MedWC"})
        self.high = self.WC.create({"name": "BTLNCK HighWC"})
        today = fields.Date.context_today(self.env["res.users"])
        self.week_start = today - timedelta(days=today.weekday())

        # capacity.planned_hours is a COMPUTED field (from mrp.workorder), so
        # it cannot be seeded directly — stage real workorders instead. 10h /
        # 30h / 60h against a 40h week => load 25% / 75% / 150%.
        product = self.env["product.product"].create(
            {"name": "BTLNCK Product", "type": "consu"})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
            "type": "normal",
        })
        mo = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        wo_start = datetime.combine(
            self.week_start + timedelta(days=1),
            datetime.min.time().replace(hour=9),
        )
        for wc, minutes in (
            (self.low, 600.0), (self.med, 1800.0), (self.high, 3600.0)
        ):
            op = self.env["mrp.routing.workcenter"].create({
                "bom_id": bom.id,
                "name": "Op %s" % wc.name,
                "workcenter_id": wc.id,
                "time_cycle_manual": minutes,
            })
            self.env["mrp.workorder"].create({
                "name": "WO %s" % wc.name,
                "production_id": mo.id,
                "workcenter_id": wc.id,
                "product_uom_id": product.uom_id.id,
                "operation_id": op.id,
                "duration_expected": minutes,
                "date_start": wo_start,
                "state": "ready",
            })

        Cap = self.env["southbrook.mes_mps.workcenter_capacity"]
        # planned_hours computes from the workorders above at create time.
        for wc in (self.low, self.med, self.high):
            Cap.create({
                "workcenter_id": wc.id,
                "week_start": self.week_start,
                "available_hours": 40.0,
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
