# SPDX-License-Identifier: LGPL-3.0-only
from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestRoe(TransactionCase):
    def setUp(self):
        super().setUp()
        self.emp = self.env["hr.employee"].create({"name": "ROE Emp"})
        self.run = self.env["southbrook.payroll.run"].create(
            {
                "period_from": date(2026, 1, 1),
                "period_to": date(2026, 1, 14),
                "pay_date": date(2026, 1, 20),
                "employee_ids": [(6, 0, [self.emp.id])],
            }
        )

    def test_compute_box_15c_aggregates_27_periods(self):
        Payslip = self.env["southbrook.payroll.payslip"]
        for _ in range(30):
            Payslip.create(
                {
                    "payroll_run_id": self.run.id,
                    "employee_id": self.emp.id,
                    "gross": 2_000.0,
                    "state": "posted",
                }
            )
        roe = self.env["southbrook.payroll.roe"].create({"employee_id": self.emp.id})
        roe.action_compute_box_15c()
        # 27 most recent of 30 -> 27 * 2000 = 54_000
        self.assertAlmostEqual(roe.total_insurable_earnings, 54_000.0, places=2)
        self.assertEqual(roe.total_insurable_hours, 27 * 80)
