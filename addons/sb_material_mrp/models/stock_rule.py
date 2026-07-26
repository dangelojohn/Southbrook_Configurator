# SPDX-License-Identifier: LGPL-3.0-only
"""Phase-2b Task 5 -- the ONLY permitted purchase.order.button_confirm()
call site in the Southbrook Materials modules (Fork-3: auto-confirm-
below-threshold, default OFF, explicitly gated).

`_run_buy` below calls `super()._run_buy(procurements)` FIRST and
UNCHANGED -- the native `purchase_stock` PO-creation/selection/pricing
logic runs exactly as it does today (verified against
addons/purchase_stock/models/stock_rule.py). Only AFTER that does this
override ever touch the resulting PO, and only to confirm one the native
code already created/updated -- never to write product_id/product_qty/
price_unit/partner_id, and never to create a purchase.order or
purchase.order.line itself.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _run_buy(self, procurements):
        result = super()._run_buy(procurements)
        self._sb_maybe_auto_confirm_buy_pos(procurements)
        return result

    def _sb_maybe_auto_confirm_buy_pos(self, procurements):
        for procurement, rule in procurements:
            supplier = procurement.values.get("supplier")
            if not supplier:
                continue
            company = rule.company_id or procurement.company_id
            if not company.sb_material_po_auto_confirm:
                continue
            if company.sb_material_po_auto_confirm_max_amount <= 0.0:
                continue
            partner = supplier.partner_id
            domain = rule._make_po_get_domain(company, procurement.values, partner)
            po = self.env["purchase.order"].sudo().search(domain, limit=1)
            if not po or po.state != "draft":
                continue
            if po.amount_total > company.sb_material_po_auto_confirm_max_amount:
                continue
            _logger.info(
                "sb_material_mrp: auto-confirming RFQ %s (%.2f <= threshold "
                "%.2f) for %s -- Phase-2b Task 5, gated, default-off.",
                po.name, po.amount_total,
                company.sb_material_po_auto_confirm_max_amount, partner.display_name,
            )
            po.message_post(
                body=(
                    "Auto-confirmed by Southbrook Materials (Phase-2b Task "
                    "5): amount %.2f <= configured threshold %.2f."
                ) % (po.amount_total, company.sb_material_po_auto_confirm_max_amount)
            )
            po.sudo().button_confirm()
