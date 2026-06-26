# SPDX-License-Identifier: LGPL-3.0-only
"""Per-employee payslip.

The payslip is the unit of computation: it owns the deduction math and
the journal-entry-ready totals. A payroll_run is a parent that loops over
employees and creates one payslip per employee for the period.
"""

from odoo import _, api, fields, models

from . import cra_calc


class SouthbrookPayrollPayslip(models.Model):
    _name = "southbrook.payroll.payslip"
    _description = "Southbrook Payslip"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("New"),
        tracking=True,
    )
    payroll_run_id = fields.Many2one(
        "southbrook.payroll.run",
        string="Payroll Run",
        ondelete="cascade",
        index=True,
    )
    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)
    contract_id = fields.Many2one("southbrook.payroll.contract", tracking=True)
    gross = fields.Float(required=True, tracking=True)
    cpp = fields.Float(compute="_compute_deductions", store=True)
    ei = fields.Float(compute="_compute_deductions", store=True)
    federal_tax = fields.Float(compute="_compute_deductions", store=True)
    provincial_tax = fields.Float(compute="_compute_deductions", store=True)
    additional_tax = fields.Float(compute="_compute_additional_tax", store=True)
    total_deductions = fields.Float(compute="_compute_totals", store=True)
    net = fields.Float(compute="_compute_totals", store=True)
    wsib_employer_premium = fields.Float(compute="_compute_employer", store=True)
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "southbrook.payroll.payslip"
                )
                vals["name"] = seq or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Deduction math
    # ------------------------------------------------------------------
    @api.depends("gross", "contract_id")
    def _compute_deductions(self):
        for rec in self:
            periods = (rec.contract_id.pay_periods_per_year or 26) if rec.contract_id else 26
            rec.cpp = cra_calc.cpp_2026(rec.gross, periods)
            # EI capped per-period at MIE/periods to absorb the YTD cap.
            ei_uncapped = cra_calc.ei_2026(rec.gross)
            ei_cap = cra_calc.EI_MAX_PREMIUM_2026 / max(1, periods)
            rec.ei = min(ei_uncapped, ei_cap)
            # Annualize gross to pick a tax bracket, then divide back.
            annual = rec.gross * periods
            fed_annual = cra_calc.federal_tax_2026(annual)
            prov_annual = cra_calc.ontario_tax_2026(annual)
            rec.federal_tax = fed_annual / periods
            rec.provincial_tax = prov_annual / periods

    @api.depends("contract_id")
    def _compute_additional_tax(self):
        for rec in self:
            raw = (rec.contract_id.additional_federal_tax_request or "") if rec.contract_id else ""
            # Strip currency symbols / commas; tolerate empty.
            cleaned = "".join(c for c in raw if c.isdigit() or c == "." or c == "-")
            try:
                rec.additional_tax = float(cleaned) if cleaned else 0.0
            except ValueError:
                rec.additional_tax = 0.0

    @api.depends("gross", "cpp", "ei", "federal_tax", "provincial_tax", "additional_tax")
    def _compute_totals(self):
        for rec in self:
            rec.total_deductions = (
                rec.cpp + rec.ei + rec.federal_tax + rec.provincial_tax + rec.additional_tax
            )
            rec.net = rec.gross - rec.total_deductions

    @api.depends("gross", "contract_id")
    def _compute_employer(self):
        for rec in self:
            rate = (rec.contract_id.wsib_rate_pct or cra_calc.WSIB_DEFAULT_RATE_PCT_2026) if rec.contract_id else cra_calc.WSIB_DEFAULT_RATE_PCT_2026
            rec.wsib_employer_premium = cra_calc.wsib_2026(rec.gross, rate)
