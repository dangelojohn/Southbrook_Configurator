# SPDX-License-Identifier: LGPL-3.0-only
"""Finance Manufacturing-Intelligence tiles (snapshot).

Mirrors the southbrook_quality MI tiles pattern: a concrete (non-abstract)
stateless model the manager dashboard queries on render. v19 forbids
inheriting an AbstractModel as a concrete Model (registry raises
TypeError - project memory note ``odoo19_abstract_model_inherit_trap``);
the southbrook.mi.engine in southbrook_manufacturing_intelligence is one
such AbstractModel, so we declare a NEW model rather than _inherit it.
"""

from datetime import timedelta, date

from odoo import api, fields, models


class SouthbrookFinanceMiTiles(models.Model):
    _name = "southbrook.finance.mi_tiles"
    _description = "Southbrook Finance MI Tiles (snapshot)"
    _rec_name = "label"

    label = fields.Char(default="Finance Snapshot", required=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        store=True,
    )

    wip_balance_current = fields.Monetary(
        compute="_compute_tiles",
        currency_field="currency_id",
        string="WIP Balance (current)",
    )
    budget_variance_ytd_pct = fields.Float(
        compute="_compute_tiles",
        digits=(8, 2),
        string="Budget Variance YTD (%)",
    )
    hst_owing_current_quarter = fields.Monetary(
        compute="_compute_tiles",
        currency_field="currency_id",
        string="HST Owing (current quarter)",
    )
    cash_position = fields.Monetary(
        compute="_compute_tiles",
        currency_field="currency_id",
        string="Cash Position",
    )
    revenue_last_30d = fields.Monetary(
        compute="_compute_tiles",
        currency_field="currency_id",
        string="Revenue (30d)",
    )
    revenue_vs_budget_30d_pct = fields.Float(
        compute="_compute_tiles",
        digits=(8, 2),
        string="Revenue vs Budget (30d %)",
    )

    @api.depends("label")
    def _compute_tiles(self):
        WipReport = self.env["southbrook.finance.wip_report"]
        Budget = self.env["southbrook.finance.budget"]
        HstReturn = self.env["southbrook.finance.hst_return"]
        AML = self.env["account.move.line"]
        Account = self.env["account.account"]

        today = fields.Date.today()
        cutoff_30 = today - timedelta(days=30)
        year_start = date(today.year, 1, 1)

        # Most-recent WIP report by as_of_date.
        wip_latest = WipReport.search([], order="as_of_date desc, id desc", limit=1)
        wip_value = wip_latest.total_wip_value if wip_latest else 0.0

        # Most-recent active budget; pct = (actual_ytd - budget_ytd) / budget_ytd.
        budget = Budget.search(
            [("state", "=", "active")],
            order="period_from desc, id desc",
            limit=1,
        )
        if budget:
            actual = sum(budget.line_ids.mapped("actual_amount"))
            planned = sum(budget.line_ids.mapped("budget_amount"))
            variance_pct = (
                ((actual - planned) / planned) * 100.0 if planned else 0.0
            )
        else:
            variance_pct = 0.0

        # Current-quarter HST.
        current_q = str(((today.month - 1) // 3) + 1)
        hst = HstReturn.search(
            [("tax_year", "=", today.year), ("quarter", "=", current_q)],
            limit=1,
        )
        hst_owing = hst.net_hst_owing if hst else 0.0

        # Cash position: sum of balance on accounts of type asset_cash.
        cash_accounts = Account.search([("account_type", "=", "asset_cash")])
        cash = 0.0
        if cash_accounts:
            cash_lines = AML.search(
                [
                    ("account_id", "in", cash_accounts.ids),
                    ("parent_state", "=", "posted"),
                    ("date", "<=", today),
                ]
            )
            cash = sum(cash_lines.mapped("balance"))

        # Revenue 30d: customer-invoice base lines.
        rev_lines = AML.search(
            [
                ("date", ">=", cutoff_30),
                ("date", "<=", today),
                ("parent_state", "=", "posted"),
                ("move_id.move_type", "in", ("out_invoice", "out_refund")),
                ("tax_line_id", "=", False),
                ("display_type", "in", (False, "product")),
            ]
        )
        revenue_30d = -sum(rev_lines.mapped("balance"))

        # Revenue vs budget for the 30-day window: approximate "budget for the
        # last 30 days" as one-twelfth of the active budget's total per month
        # touched by the window.
        if budget and budget.total_budget:
            # Crude monthly slice: total_budget / months-in-period.
            months_in_period = max(
                1,
                ((budget.period_to.year - budget.period_from.year) * 12)
                + (budget.period_to.month - budget.period_from.month)
                + 1,
            )
            monthly_budget = budget.total_budget / months_in_period
            rev_budget_pct = (
                ((revenue_30d - monthly_budget) / monthly_budget) * 100.0
                if monthly_budget
                else 0.0
            )
        else:
            rev_budget_pct = 0.0

        for rec in self:
            rec.wip_balance_current = wip_value
            rec.budget_variance_ytd_pct = variance_pct
            rec.hst_owing_current_quarter = hst_owing
            rec.cash_position = cash
            rec.revenue_last_30d = revenue_30d
            rec.revenue_vs_budget_30d_pct = rev_budget_pct
            # Silence the unused-import warning for ``year_start``: reserved
            # for a future "YTD revenue" tile.
            _ = year_start
