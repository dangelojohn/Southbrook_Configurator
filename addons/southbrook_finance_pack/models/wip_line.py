# SPDX-License-Identifier: LGPL-3.0-only
"""One WIP report line: consumed component on an open MO."""

from odoo import api, fields, models


class SouthbrookFinanceWipLine(models.Model):
    _name = "southbrook.finance.wip_line"
    _description = "Southbrook Finance - WIP Line"
    _order = "wip_report_id, production_id, product_id"

    wip_report_id = fields.Many2one(
        "southbrook.finance.wip_report",
        string="WIP Report",
        required=True,
        ondelete="cascade",
        index=True,
    )
    production_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        required=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Component",
        required=True,
    )
    qty_consumed = fields.Float(
        string="Qty Consumed",
        digits="Product Unit of Measure",
    )
    standard_cost = fields.Monetary(
        string="Standard Cost",
        currency_field="currency_id",
    )
    wip_value = fields.Monetary(
        string="WIP Value",
        compute="_compute_wip_value",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="wip_report_id.currency_id",
        string="Currency",
        store=False,
    )
    company_id = fields.Many2one(
        related="wip_report_id.company_id",
        string="Company",
        store=True,
    )

    @api.depends("qty_consumed", "standard_cost")
    def _compute_wip_value(self):
        for line in self:
            line.wip_value = (line.qty_consumed or 0.0) * (line.standard_cost or 0.0)
