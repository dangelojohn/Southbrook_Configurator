# SPDX-License-Identifier: LGPL-3.0-only
"""One row of a generated CCA depreciation schedule."""

from odoo import fields, models


class SouthbrookFinanceDepreciationLine(models.Model):
    _name = "southbrook.finance.depreciation_line"
    _description = "Southbrook Finance - Depreciation Schedule Line"
    _order = "asset_id, year"

    asset_id = fields.Many2one(
        "southbrook.finance.asset",
        string="Asset",
        required=True,
        ondelete="cascade",
        index=True,
    )
    year = fields.Integer(string="Year", required=True)
    opening_balance = fields.Monetary(
        string="Opening UCC",
        currency_field="currency_id",
    )
    cca_amount = fields.Monetary(
        string="CCA Amount",
        currency_field="currency_id",
    )
    closing_balance = fields.Monetary(
        string="Closing UCC",
        currency_field="currency_id",
    )
    posted = fields.Boolean(
        string="Posted",
        default=False,
        help="True once an account.move has been generated for this line.",
    )
    currency_id = fields.Many2one(
        related="asset_id.currency_id",
        string="Currency",
        store=False,
    )
    company_id = fields.Many2one(
        related="asset_id.company_id",
        string="Company",
        store=True,
    )

    _unique_asset_year = models.Constraint(
        "UNIQUE(asset_id, year)",
        "One depreciation line per asset per year.",
    )
