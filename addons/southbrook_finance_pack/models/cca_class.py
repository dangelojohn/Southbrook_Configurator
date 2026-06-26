# SPDX-License-Identifier: LGPL-3.0-only
"""Capital Cost Allowance (CCA) class master data.

CRA prescribes a declining-balance rate per class plus an optional half-year
rule that takes only half of the normal CCA in the asset's first year. The
Accelerated Investment Incentive (AII, 2018-2023 phasing) effectively gives
1.5x the regular first-year deduction *instead* of applying the half-year
rule -- which, against the half-year baseline (half-rate), is exactly 3x.

Class 29 is the documented exception: 50% straight-line over three years
(25/50/25 in some references, 50/50 in older statute, 50/25/25 today). We
implement the simple 50-50-0/50-50-50 case as a flag (`straight_line`) so
the asset model can branch.
"""

from odoo import fields, models


class SouthbrookFinanceCcaClass(models.Model):
    _name = "southbrook.finance.cca_class"
    _description = "Southbrook Finance - CCA Class"
    _order = "code"
    _rec_name = "name"

    name = fields.Char(string="Name", required=True)
    code = fields.Char(string="Code", required=True)
    description = fields.Text(string="Description")
    rate_pct = fields.Float(
        string="Rate (%)",
        required=True,
        help="Declining-balance rate as percent (e.g. 20.0 for Class 8).",
    )
    half_year_rule = fields.Boolean(
        string="Half-Year Rule",
        default=True,
        help="If set, the first year takes half of the normal CCA deduction.",
    )
    accelerated_investment_incentive = fields.Boolean(
        string="AII Eligible",
        default=True,
        help=(
            "Accelerated Investment Incentive (CRA, 2018-2023+ phasing): "
            "year-1 deduction = 1.5 x normal rate (equivalent to 3 x the "
            "half-year rate). When True, suspends the half-year rule for "
            "year 1."
        ),
    )
    straight_line = fields.Boolean(
        string="Straight-Line (no declining balance)",
        default=False,
        help=(
            "Class 29 (manufacturing equipment) historically depreciates "
            "straight-line over a fixed term rather than declining balance."
        ),
    )
    straight_line_years = fields.Integer(
        string="Straight-Line Years",
        default=3,
        help="Number of years over which a straight-line class fully depreciates.",
    )
    max_capital_cost = fields.Float(
        string="Max Capital Cost",
        default=0.0,
        help=(
            "Per-asset cost ceiling, e.g. Class 10.1 (passenger vehicles) is "
            "capped at $30,000. Zero means no ceiling."
        ),
    )

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "CCA class code must be unique.",
    )
