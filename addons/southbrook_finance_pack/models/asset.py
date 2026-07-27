# SPDX-License-Identifier: LGPL-3.0-only
"""CE-native asset register.

Odoo Enterprise's ``account_asset`` is unavailable on this build, so this
model carries the minimum field surface to track a capital asset and emit a
CCA schedule. JE posting is deliberately out of v1 scope - the schedule is
the artifact accounting needs at year-end; manual moves close the loop.

Schedule generation rules (see test_cca_schedule.py):
* Declining balance: ``cca_year = opening_balance * rate``
* Half-year rule: ``cca_year_1 = 0.5 * (cost * rate)``
* AII (when class is AII-eligible AND active): suspends half-year and uses
  ``cca_year_1 = 1.5 * (cost * rate)``  -- i.e. 3 x the half-year baseline.
* Straight-line (Class 29 flag): ``cca_year = cost / years`` for each year,
  half-year rule still optionally bites year 1.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SouthbrookFinanceAsset(models.Model):
    _name = "southbrook.finance.asset"
    _description = "Southbrook Finance - Capital Asset"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "acquisition_date desc, id desc"

    name = fields.Char(string="Description", required=True, tracking=True)
    code = fields.Char(
        string="Asset Code",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    cca_class_id = fields.Many2one(
        "southbrook.finance.cca_class",
        string="CCA Class",
        required=True,
        tracking=True,
    )
    acquisition_date = fields.Date(
        string="Acquisition Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    acquisition_cost = fields.Monetary(
        string="Acquisition Cost",
        required=True,
        currency_field="currency_id",
        tracking=True,
    )
    salvage_value = fields.Monetary(
        string="Salvage Value",
        default=0.0,
        currency_field="currency_id",
    )
    accumulated_depreciation = fields.Monetary(
        string="Accumulated Depreciation",
        compute="_compute_depreciation_totals",
        store=True,
        currency_field="currency_id",
    )
    net_book_value = fields.Monetary(
        string="Net Book Value",
        compute="_compute_depreciation_totals",
        store=True,
        currency_field="currency_id",
    )
    schedule_ids = fields.One2many(
        "southbrook.finance.depreciation_line",
        "asset_id",
        string="Depreciation Schedule",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_service", "In Service"),
            ("disposed", "Disposed"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Currency",
        store=True,
        readonly=True,
    )

    # ---------------------------------------------------------------------
    # Create / compute
    # ---------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code") or vals.get("code") == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "southbrook.finance.asset"
                )
                vals["code"] = seq or _("New")
        return super().create(vals_list)

    @api.depends("schedule_ids.cca_amount", "schedule_ids.posted",
                 "acquisition_cost")
    def _compute_depreciation_totals(self):
        for asset in self:
            # Accumulated depreciation is only what has actually been TAKEN —
            # i.e. POSTED schedule lines — not the whole projected schedule.
            # Summing all projected lines collapsed net_book_value to ~0 the
            # instant a schedule was generated (materially misstating book
            # value on the financial statements), even though no depreciation
            # had yet been recorded.
            accumulated = sum(
                line.cca_amount for line in asset.schedule_ids if line.posted)
            asset.accumulated_depreciation = accumulated
            asset.net_book_value = asset.acquisition_cost - accumulated

    # ---------------------------------------------------------------------
    # Schedule generation
    # ---------------------------------------------------------------------
    def _apply_cost_ceiling(self, cost):
        self.ensure_one()
        ceiling = self.cca_class_id.max_capital_cost or 0.0
        if ceiling and cost > ceiling:
            return ceiling
        return cost

    def _generate_straight_line_schedule(self, years):
        """Class 29 path: equal slices over ``straight_line_years``."""
        self.ensure_one()
        cls = self.cca_class_id
        n = cls.straight_line_years or years
        base = self._apply_cost_ceiling(self.acquisition_cost)
        if n <= 0:
            return []
        # Round the per-year slice to cents, and make the LAST depreciating
        # year absorb the rounding residual, so the schedule sums EXACTLY to the
        # base (10000/3 rounded to 3333.33 × 3 = 9999.99 otherwise leaves a
        # permanent $0.01 UCC and mis-states the final depreciation).
        per_year = round(base / n, 2)
        rows = []
        balance = round(base, 2)
        for y in range(1, years + 1):
            if y < n:
                cca = min(per_year, balance)
            elif y == n:
                cca = balance  # last depreciating year: whatever's left
            else:
                cca = 0.0
            cca = min(cca, balance)
            opening = balance
            balance = round(balance - cca, 2)
            rows.append(
                {
                    "year": y,
                    "opening_balance": opening,
                    "cca_amount": cca,
                    "closing_balance": balance,
                }
            )
        return rows

    def _generate_declining_balance_schedule(self, years):
        self.ensure_one()
        cls = self.cca_class_id
        rate = (cls.rate_pct or 0.0) / 100.0
        base = self._apply_cost_ceiling(self.acquisition_cost)
        balance = base
        rows = []
        for y in range(1, years + 1):
            opening = balance
            if y == 1:
                if cls.accelerated_investment_incentive:
                    # AII: 1.5 x normal rate; supplants half-year rule.
                    cca = base * rate * 1.5
                elif cls.half_year_rule:
                    cca = base * rate * 0.5
                else:
                    cca = base * rate
            else:
                cca = balance * rate
            cca = min(cca, balance)
            balance -= cca
            rows.append(
                {
                    "year": y,
                    "opening_balance": opening,
                    "cca_amount": cca,
                    "closing_balance": balance,
                }
            )
        return rows

    def compute_schedule_rows(self, years=10):
        """Pure function — returns row dicts, does not write to DB.

        Exposed for the test suite to verify CCA math without touching the
        ORM (and re-used by ``action_generate_schedule``).
        """
        self.ensure_one()
        if self.cca_class_id.straight_line:
            return self._generate_straight_line_schedule(years)
        return self._generate_declining_balance_schedule(years)

    def action_generate_schedule(self, years=10):
        """Regenerate the depreciation schedule.

        Wipes any unposted lines and replaces them with a freshly computed
        ``years``-long schedule. Posted lines are preserved and re-validated
        against the recomputed series (a posted line whose year falls inside
        the new schedule is left in place; the recomputed amount goes into
        the next available year). For v1 simplicity, we require ALL lines to
        be unposted before regen.
        """
        self.ensure_one()
        if not self.cca_class_id:
            raise UserError(_("Set a CCA class before generating the schedule."))
        if not self.acquisition_cost or self.acquisition_cost <= 0:
            raise UserError(_("Acquisition cost must be positive."))
        if any(line.posted for line in self.schedule_ids):
            raise UserError(
                _(
                    "Asset %s has posted depreciation lines; cannot regenerate "
                    "schedule. Reverse the postings first."
                )
                % self.code
            )
        self.schedule_ids.unlink()
        rows = self.compute_schedule_rows(years=years)
        Line = self.env["southbrook.finance.depreciation_line"]
        for row in rows:
            Line.create(
                {
                    "asset_id": self.id,
                    "year": row["year"],
                    "opening_balance": row["opening_balance"],
                    "cca_amount": row["cca_amount"],
                    "closing_balance": row["closing_balance"],
                }
            )
        self.message_post(
            body=_(
                "Generated %(n)d-year CCA schedule for class %(cls)s.",
                n=years,
                cls=self.cca_class_id.code,
            )
        )
        return True

    def action_set_in_service(self):
        for rec in self:
            rec.state = "in_service"

    def action_set_disposed(self):
        for rec in self:
            rec.state = "disposed"
