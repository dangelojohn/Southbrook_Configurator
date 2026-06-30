# SPDX-License-Identifier: LGPL-3.0-only
"""Budget line: one account x one month x one budgeted amount."""

from datetime import date
from calendar import monthrange

from odoo import api, fields, models


MONTH_SELECTION = [
    ("01", "January"),
    ("02", "February"),
    ("03", "March"),
    ("04", "April"),
    ("05", "May"),
    ("06", "June"),
    ("07", "July"),
    ("08", "August"),
    ("09", "September"),
    ("10", "October"),
    ("11", "November"),
    ("12", "December"),
]


class SouthbrookFinanceBudgetLine(models.Model):
    _name = "southbrook.finance.budget_line"
    _description = "Southbrook Finance - Budget Line"
    _order = "budget_id, account_id, period_month"

    budget_id = fields.Many2one(
        "southbrook.finance.budget",
        string="Budget",
        required=True,
        ondelete="cascade",
        index=True,
    )
    account_id = fields.Many2one(
        "account.account",
        string="Account",
        required=True,
    )
    period_month = fields.Selection(
        MONTH_SELECTION,
        string="Month",
        required=True,
    )
    budget_amount = fields.Monetary(
        string="Budget",
        required=True,
        currency_field="currency_id",
    )
    actual_amount = fields.Monetary(
        string="Actual",
        compute="_compute_actual",
        currency_field="currency_id",
    )
    variance = fields.Monetary(
        string="Variance",
        compute="_compute_variance",
        currency_field="currency_id",
    )
    variance_pct = fields.Float(
        string="Variance %",
        compute="_compute_variance",
        digits=(8, 2),
    )
    currency_id = fields.Many2one(
        related="budget_id.currency_id",
        string="Currency",
        store=False,
    )
    company_id = fields.Many2one(
        related="budget_id.company_id",
        string="Company",
        store=True,
    )

    # ---------------------------------------------------------------------
    # Computed
    # ---------------------------------------------------------------------
    def _month_window(self):
        """Return (date_start, date_end) for this line's month within the budget's tax_year."""
        self.ensure_one()
        # The budget carries period_from/period_to; we treat the month as
        # belonging to whichever calendar year the budget's period_from is in.
        # For multi-year budgets the user creates one line per (account, month)
        # they care about; this is the canonical convention for v1.
        if not self.budget_id.period_from or not self.period_month:
            return (False, False)
        year = self.budget_id.period_from.year
        month = int(self.period_month)
        last_day = monthrange(year, month)[1]
        return (date(year, month, 1), date(year, month, last_day))

    @api.depends("budget_id.period_from", "account_id", "period_month")
    def _compute_actual(self):
        AML = self.env["account.move.line"]
        for line in self:
            if not line.account_id or not line.period_month or not line.budget_id.period_from:
                line.actual_amount = 0.0
                continue
            start, end = line._month_window()
            domain = [
                ("account_id", "=", line.account_id.id),
                ("date", ">=", start),
                ("date", "<=", end),
                ("parent_state", "=", "posted"),
                ("company_id", "=", line.budget_id.company_id.id),
            ]
            # Sum balance (debit-credit) -- works for any account type. Tests
            # may pre-stamp account.move.line records and rely on this aggregate.
            total = sum(AML.search(domain).mapped("balance"))
            line.actual_amount = total

    @api.depends("budget_amount", "actual_amount")
    def _compute_variance(self):
        for line in self:
            line.variance = line.actual_amount - line.budget_amount
            if line.budget_amount:
                line.variance_pct = (line.variance / line.budget_amount) * 100.0
            else:
                line.variance_pct = 0.0
