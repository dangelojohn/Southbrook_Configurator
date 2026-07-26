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
            # I-1 (final review, 2026-07-26): `_run_buy` fires for EVERY buy
            # procurement (MTO, sale-driven dropship, manual reordering,
            # MRO/stationery...), not just material-component orderpoints --
            # but the res.company help text implies material RFQs only.
            # Scope the confirm: only auto-confirm when this is genuinely a
            # MATERIAL RFQ, i.e. every real (non-section/note) line's
            # product resolves to a southbrook.kitchen.material via the
            # established resolver (product.product._resolve_material():
            # variant-attribute path first, product_tmpl_id.material_id
            # fallback). If ANY line does not resolve -- or the PO has no
            # real product lines at all -- SKIP auto-confirm (fail-safe:
            # leave draft). We never attempt to split a mixed PO.
            material_lines = po.order_line.filtered(lambda l: not l.display_type)
            if not material_lines or any(
                not (line.product_id and line.product_id._resolve_material())
                for line in material_lines
            ):
                continue
            if po.amount_total > company.sb_material_po_auto_confirm_max_amount:
                continue
            if po.amount_total <= 0.0:
                # Fail-safe lower bound: a zero/negative-amount draft PO must
                # NEVER be auto-confirmed, no matter the threshold setting
                # (0.0 <= threshold is otherwise True for any positive
                # threshold). Leave it draft for a human to review.
                continue
            # Residual (v1, accepted): `_make_po_get_domain` follows native
            # `purchase_stock` PO-merge scoping. If native merges this run's
            # procurement line onto a PRE-EXISTING human draft RFQ for the
            # same vendor/company/currency (native grouping behaviour), the
            # whole PO -- including the human's other lines -- gets
            # confirmed here. This mirrors native grouping semantics exactly
            # and is accepted for v1; revisit if it causes surprises.
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
