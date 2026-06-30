# SPDX-License-Identifier: LGPL-3.0-only
"""GST/HST Return aggregator.

Computes period totals from posted invoices and bills carrying Canadian
HST tax lines. Output (collected) and input (ITC) totals are derived
straight from ``account.move.line.tax_line_id`` -- so the figures match
whatever taxes l10n_ca has installed (the canonical CRA buckets).
"""

from datetime import date
from calendar import monthrange

from odoo import _, api, fields, models
from odoo.exceptions import UserError


QUARTER_MONTHS = {
    "1": (1, 3),
    "2": (4, 6),
    "3": (7, 9),
    "4": (10, 12),
}


class SouthbrookFinanceHstReturn(models.Model):
    _name = "southbrook.finance.hst_return"
    _description = "Southbrook Finance - HST Return"
    _order = "tax_year desc, quarter desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    tax_year = fields.Integer(
        string="Tax Year",
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    quarter = fields.Selection(
        [
            ("1", "Q1 (Jan-Mar)"),
            ("2", "Q2 (Apr-Jun)"),
            ("3", "Q3 (Jul-Sep)"),
            ("4", "Q4 (Oct-Dec)"),
        ],
        required=True,
    )
    period_from = fields.Date(string="Period From", required=True)
    period_to = fields.Date(string="Period To", required=True)
    total_sales = fields.Monetary(
        string="Total Sales (taxable)",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    hst_collected = fields.Monetary(
        string="HST Collected",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    hst_paid_itc = fields.Monetary(
        string="ITC (HST Paid)",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    net_hst_owing = fields.Monetary(
        string="Net HST Owing",
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("filed", "Filed"), ("paid", "Paid")],
        default="draft",
        required=True,
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

    _unique_period = models.Constraint(
        "UNIQUE(tax_year, quarter, company_id)",
        "One HST return per company per quarter.",
    )

    # ---------------------------------------------------------------------
    # Create / lifecycle
    # ---------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                # Build seq code as HST/{YYYY}/Q{n}
                year = vals.get("tax_year") or fields.Date.today().year
                q = vals.get("quarter") or "1"
                seq = self.env["ir.sequence"].next_by_code("southbrook.finance.hst_return")
                vals["name"] = seq or "HST/%s/Q%s" % (year, q)
            # Auto-set period_from/to from year+quarter if missing.
            if not vals.get("period_from") or not vals.get("period_to"):
                year = vals.get("tax_year") or fields.Date.today().year
                q = vals.get("quarter") or "1"
                m_start, m_end = QUARTER_MONTHS[q]
                vals.setdefault("period_from", date(year, m_start, 1))
                vals.setdefault(
                    "period_to",
                    date(year, m_end, monthrange(year, m_end)[1]),
                )
        return super().create(vals_list)

    # ---------------------------------------------------------------------
    # Totals
    # ---------------------------------------------------------------------
    @api.depends("period_from", "period_to", "company_id")
    def _compute_totals(self):
        AML = self.env["account.move.line"]
        for rec in self:
            if not rec.period_from or not rec.period_to:
                rec.total_sales = 0.0
                rec.hst_collected = 0.0
                rec.hst_paid_itc = 0.0
                rec.net_hst_owing = 0.0
                continue
            base_domain = [
                ("date", ">=", rec.period_from),
                ("date", "<=", rec.period_to),
                ("parent_state", "=", "posted"),
                ("company_id", "=", rec.company_id.id),
            ]
            # Output tax: tax lines on customer invoices.
            out_lines = AML.search(
                base_domain
                + [
                    ("tax_line_id", "!=", False),
                    ("move_id.move_type", "in", ("out_invoice", "out_refund")),
                ]
            )
            # Input tax: tax lines on vendor bills.
            in_lines = AML.search(
                base_domain
                + [
                    ("tax_line_id", "!=", False),
                    ("move_id.move_type", "in", ("in_invoice", "in_refund")),
                ]
            )
            # Output tax sits as a credit on the invoice (balance is negative
            # in the standard sign convention for sales tax payable); flip
            # sign so we report a positive "collected" figure.
            rec.hst_collected = -sum(out_lines.mapped("balance"))
            # ITC lines are debits on bills (positive balance); positive ITC.
            rec.hst_paid_itc = sum(in_lines.mapped("balance"))
            # Total taxable sales = the BASE of those sales tax lines (the
            # base_line subtotal on the move's line where tax_ids is set).
            sale_base_lines = AML.search(
                base_domain
                + [
                    ("tax_ids", "!=", False),
                    ("tax_line_id", "=", False),
                    ("move_id.move_type", "in", ("out_invoice", "out_refund")),
                ]
            )
            rec.total_sales = -sum(sale_base_lines.mapped("balance"))
            rec.net_hst_owing = rec.hst_collected - rec.hst_paid_itc

    def action_compute(self):
        # Force recompute (cache invalidation) then return self for chaining.
        self.invalidate_recordset(
            ["total_sales", "hst_collected", "hst_paid_itc", "net_hst_owing"]
        )
        # Touch a depends-trigger field to fire the @api.depends cycle.
        for rec in self:
            rec._compute_totals()
        return True

    def action_file(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft returns can be filed."))
            rec.state = "filed"

    def action_mark_paid(self):
        for rec in self:
            if rec.state != "filed":
                raise UserError(_("Only filed returns can be marked paid."))
            rec.state = "paid"
