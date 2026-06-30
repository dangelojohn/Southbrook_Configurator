# SPDX-License-Identifier: LGPL-3.0-only
from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestT4Preview(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Employee = self.env["hr.employee"]
        self.Contract = self.env["southbrook.payroll.contract"]
        self.Run = self.env["southbrook.payroll.run"]
        self.Payslip = self.env["southbrook.payroll.payslip"]
        self.T4 = self.env["southbrook.payroll.t4_preview"]
        self.emp = self.Employee.create({"name": "T4 Emp"})
        self.Contract.create(
            {
                "employee_id": self.emp.id,
                "date_start": date(2026, 1, 1),
                "wage": 52_000.0,
                "state": "active",
                "pay_periods_per_year": 26,
            }
        )

    def _post_slips(self, count, gross_each):
        # Manually create posted payslips with a synthetic run.
        run = self.Run.create(
            {
                "period_from": date(2026, 1, 1),
                "period_to": date(2026, 1, 14),
                "pay_date": date(2026, 1, 20),
                "employee_ids": [(6, 0, [self.emp.id])],
            }
        )
        run.state = "computed"
        for _ in range(count):
            self.Payslip.create(
                {
                    "payroll_run_id": run.id,
                    "employee_id": self.emp.id,
                    "gross": gross_each,
                    "state": "posted",
                }
            )
        return run

    def test_t4_box_14_sums_gross(self):
        self._post_slips(26, 2000.0)
        t4 = self.T4.generate_for_employee_year(self.emp.id, 2026)
        self.assertAlmostEqual(t4.box_14_employment_income, 26 * 2000.0, places=2)

    def test_t4_box_22_sums_all_taxes(self):
        self._post_slips(26, 2000.0)
        t4 = self.T4.generate_for_employee_year(self.emp.id, 2026)
        slips = self.Payslip.search([("employee_id", "=", self.emp.id)])
        expected = sum(
            s.federal_tax + s.provincial_tax + s.additional_tax for s in slips
        )
        self.assertAlmostEqual(t4.box_22_income_tax, expected, places=2)
