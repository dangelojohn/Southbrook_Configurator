# SPDX-License-Identifier: LGPL-3.0-only
"""Tax bracket master data exposed in the Odoo UI for transparency.

The bracket schedule is owned by ``cra_calc.py`` and seeded into this
table via ``data/cra_brackets_2026.xml``. The model is read-mostly: a
Payroll Manager can browse it to audit which schedule is in force; only
a future-year XML update should mutate the rows.

Manual editing of these rows does NOT alter the calculator's behaviour
(the calculator reads from the Python constants, not the table).  The
table is intentionally informational so a hand-edit cannot quietly
mis-tax a payroll cycle.
"""

from odoo import api, fields, models


class SouthbrookPayrollTaxBracket(models.Model):
    _name = "southbrook.payroll.tax_bracket"
    _description = "Southbrook Payroll Tax Bracket (informational)"
    _order = "year desc, jurisdiction, threshold"

    name = fields.Char(compute="_compute_name", store=True)
    jurisdiction = fields.Selection(
        [("federal", "Federal (CRA)"), ("ontario", "Ontario")],
        required=True,
    )
    year = fields.Integer(required=True, default=2026)
    threshold = fields.Float(
        string="Upper Threshold",
        help="Annual income upper bound for this bracket. Use 0 to denote "
             "the open-ended top bracket (no upper cap).",
        required=True,
    )
    rate = fields.Float(
        string="Marginal Rate",
        digits=(6, 4),
        required=True,
    )
    cumulative = fields.Float(
        string="Cumulative Tax at Lower Bound",
        digits=(12, 4),
        help="Tax owed on income at the bottom of this bracket "
             "(i.e. sum of (width * rate) of all lower brackets).",
    )

    @api.depends("jurisdiction", "year", "threshold")
    def _compute_name(self):
        for rec in self:
            label = "Top" if not rec.threshold else "<= ${:,.0f}".format(rec.threshold)
            rec.name = "{} {} {}".format(rec.year, rec.jurisdiction, label)
