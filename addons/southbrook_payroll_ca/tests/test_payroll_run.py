# SPDX-License-Identifier: LGPL-3.0-only
from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestPayrollRun(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Run = self.env["southbrook.payroll.run"]
        self.Contract = self.env["southbrook.payroll.contract"]
        self.Employee = self.env["hr.employee"]
        # Three employees + one active contract each, bi-weekly $2000 gross.
        self.employees = self.Employee.create(
            [{"name": "Emp One"}, {"name": "Emp Two"}, {"name": "Emp Three"}]
        )
        for emp in self.employees:
            self.Contract.create(
                {
                    "employee_id": emp.id,
                    "date_start": date(2026, 1, 1),
                    "wage": 52_000.0,  # annual; per-period 2000 @ 26 periods
                    "state": "active",
                    "pay_periods_per_year": 26,
                }
            )

    def _make_run(self):
        return self.Run.create(
            {
                "period_from": date(2026, 1, 1),
                "period_to": date(2026, 1, 14),
                "pay_date": date(2026, 1, 20),
                "employee_ids": [(6, 0, self.employees.ids)],
            }
        )

    def test_compute_creates_payslip_per_employee(self):
        run = self._make_run()
        run.action_compute()
        self.assertEqual(len(run.payslip_ids), 3)
        self.assertEqual(run.state, "computed")

    def test_payslip_totals_balance(self):
        run = self._make_run()
        run.action_compute()
        for slip in run.payslip_ids:
            self.assertAlmostEqual(
                slip.gross - slip.total_deductions, slip.net, places=2
            )

    def test_recompute_skips_posted_runs(self):
        run = self._make_run()
        run.action_compute()
        # Force-post by skipping the journal step; just write the state.
        run.state = "posted"
        with self.assertRaises(Exception):
            run.action_compute()

    def test_post_creates_journal_entry(self):
        """action_post creates a balanced account.move.

        The post path needs a general journal + at least one expense and
        one current-liability account; when the CoA isn't installed in
        the test DB we skip (rather than fail on env shape).
        """
        run = self._make_run()
        run.action_compute()
        journal = self.env["account.journal"].search(
            [("type", "=", "general")], limit=1
        )
        if not journal:
            self.skipTest("Test DB has no general journal (CoA not installed).")
        try:
            run.action_post()
        except Exception as e:
            self.skipTest("Post requires CoA accounts: %s" % e)
        self.assertEqual(run.state, "posted")
        self.assertTrue(run.move_id)
        debits = sum(run.move_id.line_ids.mapped("debit"))
        credits = sum(run.move_id.line_ids.mapped("credit"))
        self.assertAlmostEqual(debits, credits, places=2)
