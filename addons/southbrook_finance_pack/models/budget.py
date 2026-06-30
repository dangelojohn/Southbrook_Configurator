# SPDX-License-Identifier: LGPL-3.0-only
"""Operating budget header.

Odoo CE 19 does not ship ``account_budget``; this is the Southbrook bridge.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SouthbrookFinanceBudget(models.Model):
    _name = "southbrook.finance.budget"
    _description = "Southbrook Finance - Operating Budget"
    _order = "period_from desc, id desc"

    name = fields.Char(string="Name", required=True)
    period_from = fields.Date(string="Period From", required=True)
    period_to = fields.Date(string="Period To", required=True)
    line_ids = fields.One2many(
        "southbrook.finance.budget_line",
        "budget_id",
        string="Lines",
    )
    total_budget = fields.Monetary(
        string="Total Budget",
        compute="_compute_total_budget",
        store=True,
        currency_field="currency_id",
    )
    total_actual = fields.Monetary(
        string="Total Actual",
        compute="_compute_total_budget",
        currency_field="currency_id",
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
    )
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("closed", "Closed")],
        default="draft",
    )

    @api.depends("line_ids.budget_amount", "line_ids.actual_amount")
    def _compute_total_budget(self):
        for budget in self:
            budget.total_budget = sum(line.budget_amount for line in budget.line_ids)
            budget.total_actual = sum(line.actual_amount for line in budget.line_ids)

    @api.constrains("period_from", "period_to")
    def _check_period_order(self):
        for rec in self:
            if rec.period_from and rec.period_to and rec.period_from > rec.period_to:
                raise ValidationError(
                    _("Budget %s: period start must be on or before period end.")
                    % rec.name
                )

    def action_activate(self):
        for rec in self:
            rec.state = "active"

    def action_close(self):
        for rec in self:
            rec.state = "closed"
