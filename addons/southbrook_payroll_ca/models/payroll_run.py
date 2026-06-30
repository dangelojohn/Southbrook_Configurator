# SPDX-License-Identifier: LGPL-3.0-only
"""Payroll Run — a period containing one payslip per employee.

State machine:
    draft -> computed -> posted -> paid

`action_compute` populates payslips for every employee in the run from
their currently-active southbrook.payroll.contract. `action_post` reads each payslip's
totals and books a single balanced account.move (wage expense Dr,
deductions payable Cr, net payable to employees Cr). `action_pay` is a
soft transition; integrating with bank-pay-out is left to a downstream
step.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SouthbrookPayrollRun(models.Model):
    _name = "southbrook.payroll.run"
    _description = "Southbrook Payroll Run"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "period_to desc, id desc"

    name = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
    )
    period_from = fields.Date(required=True, tracking=True)
    period_to = fields.Date(required=True, tracking=True)
    pay_date = fields.Date(required=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("computed", "Computed"),
            ("posted", "Posted"),
            ("paid", "Paid"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    employee_ids = fields.Many2many(
        "hr.employee",
        "southbrook_payroll_run_employee_rel",
        "run_id",
        "employee_id",
        required=True,
    )
    payslip_ids = fields.One2many(
        "southbrook.payroll.payslip",
        "payroll_run_id",
        string="Payslips",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)

    total_gross = fields.Monetary(compute="_compute_totals", store=True)
    total_deductions = fields.Monetary(compute="_compute_totals", store=True)
    total_net = fields.Monetary(compute="_compute_totals", store=True)
    total_eht = fields.Monetary(compute="_compute_totals", store=True)
    total_wsib = fields.Monetary(compute="_compute_totals", store=True)

    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code("southbrook.payroll.run")
                vals["name"] = seq or _("New")
        return super().create(vals_list)

    @api.depends(
        "payslip_ids.gross",
        "payslip_ids.total_deductions",
        "payslip_ids.net",
        "payslip_ids.wsib_employer_premium",
    )
    def _compute_totals(self):
        # EHT is annual-payroll based; we expose YTD projection here.
        from .cra_calc import eht_ontario_2026
        for rec in self:
            rec.total_gross = sum(rec.payslip_ids.mapped("gross"))
            rec.total_deductions = sum(rec.payslip_ids.mapped("total_deductions"))
            rec.total_net = sum(rec.payslip_ids.mapped("net"))
            rec.total_wsib = sum(rec.payslip_ids.mapped("wsib_employer_premium"))
            # YTD projection: this run's gross * estimated 26 periods, only
            # informative when displayed on a single-period run.
            annual_proj = rec.total_gross * 26
            rec.total_eht = eht_ontario_2026(annual_proj)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_compute(self):
        Payslip = self.env["southbrook.payroll.payslip"]
        Contract = self.env["southbrook.payroll.contract"]
        for run in self:
            if run.state == "posted":
                raise UserError(
                    _("Cannot recompute payroll run %s: already posted.", run.name)
                )
            # Drop any existing payslips so a recompute is idempotent.
            run.payslip_ids.unlink()
            for emp in run.employee_ids:
                # Look up an active contract that overlaps the period:
                # date_start <= period_to AND (date_end is null OR date_end >= period_from)
                contract = Contract.search(
                    [
                        ("employee_id", "=", emp.id),
                        ("state", "=", "active"),
                        ("date_start", "<=", run.period_to),
                        "|",
                        ("date_end", "=", False),
                        ("date_end", ">=", run.period_from),
                    ],
                    limit=1,
                )
                if not contract:
                    contract = Contract.search(
                        [("employee_id", "=", emp.id)],
                        order="date_start desc",
                        limit=1,
                    )
                # Per-period gross: contract.wage / pay_periods. If no
                # contract, default 0 (payslip will surface as $0).
                periods = (contract.pay_periods_per_year or 26) if contract else 26
                gross = (contract.wage / periods) if (contract and contract.wage) else 0.0
                Payslip.create(
                    {
                        "payroll_run_id": run.id,
                        "employee_id": emp.id,
                        "contract_id": contract.id if contract else False,
                        "gross": gross,
                        "state": "computed",
                    }
                )
            run.state = "computed"

    def action_post(self):
        Move = self.env["account.move"]
        for run in self:
            if run.state not in ("computed",):
                raise UserError(
                    _("Run %s must be Computed before Post.", run.name)
                )
            if not run.payslip_ids:
                raise UserError(_("Run %s has no payslips to post.", run.name))
            # Build a single balanced journal entry.
            journal = self.env["account.journal"].search(
                [("type", "=", "general"), ("company_id", "=", run.company_id.id)],
                limit=1,
            )
            if not journal:
                raise UserError(_("No general journal configured for company."))
            # Use the first available expense / liability accounts as
            # placeholders; integrators wire these to real CoA accounts.
            expense_acc = self.env["account.account"].search(
                [
                    ("account_type", "=", "expense"),
                    ("company_ids", "in", run.company_id.id),
                ],
                limit=1,
            )
            payable_acc = self.env["account.account"].search(
                [
                    ("account_type", "=", "liability_current"),
                    ("company_ids", "in", run.company_id.id),
                ],
                limit=1,
            )
            if not expense_acc or not payable_acc:
                raise UserError(
                    _("Set up at least one expense + one current-liability account.")
                )
            lines = [
                (0, 0, {
                    "name": _("Payroll wage expense %s") % run.name,
                    "account_id": expense_acc.id,
                    "debit": run.total_gross,
                    "credit": 0.0,
                }),
                (0, 0, {
                    "name": _("Payroll net payable %s") % run.name,
                    "account_id": payable_acc.id,
                    "debit": 0.0,
                    "credit": run.total_net,
                }),
                (0, 0, {
                    "name": _("Payroll deductions payable %s") % run.name,
                    "account_id": payable_acc.id,
                    "debit": 0.0,
                    "credit": run.total_deductions,
                }),
            ]
            move = Move.create(
                {
                    "journal_id": journal.id,
                    "date": run.pay_date,
                    "ref": run.name,
                    "line_ids": lines,
                }
            )
            run.move_id = move.id
            run.payslip_ids.write({"state": "posted"})
            run.state = "posted"

    def action_pay(self):
        for run in self:
            if run.state != "posted":
                raise UserError(
                    _("Run %s must be Posted before Pay.", run.name)
                )
            run.payslip_ids.write({"state": "paid"})
            run.state = "paid"
