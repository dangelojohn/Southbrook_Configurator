# SPDX-License-Identifier: LGPL-3.0-only
"""Southbrook-owned payroll contract.

Odoo 19 CE removed the ``hr_contract`` module — only the ``hr.contract.type``
stub remains. Rather than re-use ``hr.version`` (which has different per-period
snapshot semantics), we define our own ``southbrook.payroll.contract`` model
that holds the Canadian payroll fields and a minimal employment period.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .cra_calc import FEDERAL_BPA_2026, ONTARIO_BPA_2026, WSIB_DEFAULT_RATE_PCT_2026


class SouthbrookPayrollContract(models.Model):
    _name = "southbrook.payroll.contract"
    _description = "Southbrook Canadian Payroll Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        tracking=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        tracking=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    date_start = fields.Date(string="Start Date", required=True, tracking=True)
    date_end = fields.Date(string="End Date", tracking=True)
    wage = fields.Monetary(
        string="Annual Wage",
        required=True,
        tracking=True,
        help="Gross annual wage; bi-weekly gross = wage / 26.",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("terminated", "Terminated"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Canadian payroll fields (carried forward from the original
    # hr.contract extension; see CRA-2026 brackets for defaults).
    # ------------------------------------------------------------------
    cra_td1_personal_amount_federal = fields.Float(
        string="TD1 Federal Personal Amount",
        default=FEDERAL_BPA_2026,
        help="Federal basic personal amount per the employee's TD1. "
             "Defaults to the CRA-published 2026 value; adjust if the "
             "employee claimed an additional amount (e.g. spousal).",
    )
    cra_td1_personal_amount_ontario = fields.Float(
        string="TD1-ON Personal Amount",
        default=ONTARIO_BPA_2026,
        help="Ontario basic personal amount per the employee's TD1-ON.",
    )
    additional_federal_tax_request = fields.Char(
        string="Additional Federal Tax (per period)",
        help="Optional fixed dollar amount the employee asked CRA to "
             "withhold each pay period (TD1 Page 2). Stored as Char so "
             "callers can record source ('$25.00 / period — TD1 Jan 2026') "
             "alongside the value.",
    )
    pay_periods_per_year = fields.Integer(
        string="Pay Periods / Year",
        default=26,
        help="26 for bi-weekly, 52 for weekly, 24 for semi-monthly, "
             "12 for monthly.",
    )
    wsib_rate_pct = fields.Float(
        string="WSIB Rate (%)",
        default=WSIB_DEFAULT_RATE_PCT_2026,
        digits=(6, 4),
        help="WSIB premium rate per $100 of insurable earnings. Default "
             "0.95 = Ontario Rate Group 533 (Wood Cabinets Mfg) 2026.",
    )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "southbrook.payroll.contract"
                )
                vals["name"] = seq or _("New")
        return super().create(vals_list)

    @api.constrains("date_start", "date_end")
    def _check_date_range(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(
                    _("Contract %s: end date (%s) cannot be before start date (%s).",
                      rec.name, rec.date_end, rec.date_start)
                )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_activate(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(
                    _("Contract %s cannot be activated from state %s.",
                      rec.name, rec.state)
                )
            rec.state = "active"

    def action_terminate(self):
        for rec in self:
            if rec.state != "active":
                raise UserError(
                    _("Contract %s cannot be terminated from state %s.",
                      rec.name, rec.state)
                )
            rec.state = "terminated"
