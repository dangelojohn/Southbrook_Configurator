# SPDX-License-Identifier: LGPL-3.0-only
"""Rebate ledger — $X per cabinet on Marathon-spec'd confirmed sales."""
from odoo import api, fields, models


class MarathonRebate(models.Model):
    _name = "kitchenforge.marathon.rebate"
    _description = "KitchenForge Marathon Rebate Entry"
    _order = "create_date desc"
    _rec_name = "label"

    label = fields.Char(required=True, default="rebate")
    sale_order_id = fields.Many2one(
        "sale.order", index=True, ondelete="set null", required=True)
    project_id = fields.Many2one(
        "project.project", index=True, ondelete="set null")
    cabinet_count = fields.Integer(required=True, default=0)
    rate_per_cabinet_usd = fields.Float(required=True, default=0.0)
    amount_usd = fields.Float(
        compute="_compute_amount", store=True, readonly=True)
    period = fields.Char(
        help="YYYY-MM, used for monthly reconciliation grouping.",
        index=True)
    reconciled = fields.Boolean(default=False, index=True)
    reconciled_at = fields.Datetime()
    note = fields.Char()

    @api.depends("cabinet_count", "rate_per_cabinet_usd")
    def _compute_amount(self):
        for rec in self:
            rec.amount_usd = (rec.cabinet_count or 0) * (rec.rate_per_cabinet_usd or 0.0)

    @api.model
    def credit_for_sale(self, sale_order):
        """Idempotently credit a rebate for one confirmed sale order."""
        existing = self.search(
            [("sale_order_id", "=", sale_order.id)], limit=1)
        if existing:
            return existing
        cfg = self.env["kitchenforge.marathon.channel.config"].sudo().get_active()
        if not cfg.enabled:
            return self.browse()
        # Count cabinet lines (any line whose product is config_ok'd template).
        cabinet_count = sum(
            int(line.product_uom_qty) for line in sale_order.order_line
            if line.product_id.product_tmpl_id.config_ok
        )
        if not cabinet_count:
            return self.browse()
        period = sale_order.date_order.strftime("%Y-%m") if sale_order.date_order else ""
        return self.sudo().create({
            "label": f"rebate/{sale_order.name}",
            "sale_order_id": sale_order.id,
            "project_id": sale_order.kitchenforge_project_id.id or False,
            "cabinet_count": cabinet_count,
            "rate_per_cabinet_usd": cfg.rebate_per_cabinet_usd,
            "period": period,
        })

    @api.model
    def monthly_summary(self, period=None):
        """Return list of {period, count, amount} dicts for reconciliation."""
        domain = []
        if period:
            domain.append(("period", "=", period))
        rows = self.read_group(
            domain, ["period", "cabinet_count:sum", "amount_usd:sum"],
            ["period"], orderby="period desc")
        return rows
