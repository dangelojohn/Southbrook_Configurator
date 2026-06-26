# SPDX-License-Identifier: LGPL-3.0-only
"""T4 slip preview — informational, not CRA-filing-ready.

Aggregates posted payslips for a tax year into the box numbers that
appear on a T4 slip. Filing the actual T4 (XML upload to CRA, paper-form
print) is out of scope for v1; this model is the data layer that a
filer can read from.
"""

from odoo import _, api, fields, models


class SouthbrookPayrollT4Preview(models.Model):
    _name = "southbrook.payroll.t4_preview"
    _description = "Southbrook T4 Slip Preview"
    _order = "tax_year desc, employee_id"

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", required=True, index=True)
    tax_year = fields.Integer(required=True, default=2026)

    box_14_employment_income = fields.Float(string="Box 14 - Employment Income")
    box_16_cpp = fields.Float(string="Box 16 - CPP")
    box_18_ei = fields.Float(string="Box 18 - EI")
    box_22_income_tax = fields.Float(string="Box 22 - Income Tax")
    box_24_ei_insurable_earnings = fields.Float(string="Box 24 - EI Insurable")
    box_26_cpp_pensionable_earnings = fields.Float(string="Box 26 - CPP Pensionable")

    _unique_employee_year = models.Constraint(
        "UNIQUE(employee_id, tax_year)",
        "Only one T4 preview per employee per tax year.",
    )

    @api.depends("employee_id", "tax_year")
    def _compute_name(self):
        for rec in self:
            code = rec.employee_id.id and (rec.employee_id.barcode or str(rec.employee_id.id))
            rec.name = "T4/%s/%s" % (rec.tax_year, code or "?")

    def action_generate_for_year(self, year=None):
        """Aggregate posted payslips into T4 boxes for the given year."""
        year = year or fields.Date.context_today(self).year
        Payslip = self.env["southbrook.payroll.payslip"]
        for rec in self:
            slips = Payslip.search(
                [
                    ("employee_id", "=", rec.employee_id.id),
                    ("state", "in", ("posted", "paid")),
                    ("payroll_run_id.pay_date", ">=", "%d-01-01" % year),
                    ("payroll_run_id.pay_date", "<=", "%d-12-31" % year),
                ]
            )
            gross = sum(slips.mapped("gross"))
            cpp = sum(slips.mapped("cpp"))
            ei = sum(slips.mapped("ei"))
            fed = sum(slips.mapped("federal_tax"))
            prov = sum(slips.mapped("provincial_tax"))
            addl = sum(slips.mapped("additional_tax"))
            rec.write(
                {
                    "tax_year": year,
                    "box_14_employment_income": gross,
                    "box_16_cpp": cpp,
                    "box_18_ei": ei,
                    "box_22_income_tax": fed + prov + addl,
                    "box_24_ei_insurable_earnings": gross,
                    "box_26_cpp_pensionable_earnings": gross,
                }
            )

    @api.model
    def generate_for_employee_year(self, employee_id, year):
        """Create-or-update one T4 preview for (employee, year)."""
        rec = self.search(
            [("employee_id", "=", employee_id), ("tax_year", "=", year)],
            limit=1,
        )
        if not rec:
            rec = self.create({"employee_id": employee_id, "tax_year": year})
        rec.action_generate_for_year(year)
        return rec
