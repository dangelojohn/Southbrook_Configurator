# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for budget variance computation."""

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("southbrook", "post_install", "-at_install")
class TestBudget(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Budget = self.env["southbrook.finance.budget"]
        self.Line = self.env["southbrook.finance.budget_line"]
        # Reuse an existing expense account -- on a fresh CE install the
        # demo CoA may be empty, so create a stub account.account record.
        Account = self.env["account.account"]
        # v19: account.account.company_id was replaced by a many2many
        # `company_ids`. Use ('company_ids', 'in', ...) for search and
        # ((6, 0, [...])) for create.
        existing = Account.search(
            [
                ("account_type", "=", "expense"),
                ("company_ids", "in", self.env.company.id),
            ],
            limit=1,
        )
        if existing:
            self.account = existing
        else:
            self.account = Account.create(
                {
                    "name": "Test Expense",
                    "code": "TST-EXP",
                    "account_type": "expense",
                    "company_ids": [(6, 0, [self.env.company.id])],
                }
            )

    def test_variance_computation(self):
        """Budget $10K, actual $11K -> variance +$1K, pct +10%.

        The computation here proves the *formula*; we set actual_amount
        to a known value by patching it through a partial dependency
        (actual is computed from AML which the test harness doesn't have
        a clean way to stamp without a journal). To keep this hermetic
        we directly verify the variance math given an `actual_amount` we
        force on the line via cache write.
        """
        budget = self.Budget.create(
            {
                "name": "FY2026 Test Budget",
                "period_from": date(2026, 1, 1),
                "period_to": date(2026, 12, 31),
            }
        )
        line = self.Line.create(
            {
                "budget_id": budget.id,
                "account_id": self.account.id,
                "period_month": "01",
                "budget_amount": 10000.0,
            }
        )
        # Verify the formula: variance = actual - budget; pct = variance / budget * 100.
        # We simulate actual=11000 by stamping a dummy actual_amount via
        # cache.set then re-running _compute_variance manually.
        line._compute_actual()  # baseline (likely 0.0 with no moves)
        line.actual_amount = 11000.0  # in-memory override on the computed
        line._compute_variance()
        self.assertAlmostEqual(line.variance, 1000.0, places=2)
        self.assertAlmostEqual(line.variance_pct, 10.0, places=2)

    def test_variance_with_zero_budget_does_not_divide_by_zero(self):
        budget = self.Budget.create(
            {
                "name": "Zero-budget test",
                "period_from": date(2026, 1, 1),
                "period_to": date(2026, 12, 31),
            }
        )
        line = self.Line.create(
            {
                "budget_id": budget.id,
                "account_id": self.account.id,
                "period_month": "02",
                "budget_amount": 0.0,
            }
        )
        line.actual_amount = 500.0
        line._compute_variance()
        self.assertEqual(line.variance, 500.0)
        self.assertEqual(line.variance_pct, 0.0)
