# SPDX-License-Identifier: LGPL-3.0-only
"""
product.pricelist.item extension — the refacing margin-target computation.

This file IS custom routine #2 per Build Spec section 4. The only
non-declarative pricing rule in the entire pricelist suite — every
other channel is pure data + standard Odoo pricelist mechanics.

The refacing channel (CTHS / Canadian Tire Home Services) sets per-SF
door pricing live to hit a 35% margin off the current cost. Cost
changes (raw material, supplier moves) automatically flow into the
refacing price without a re-seed.
"""
from odoo import api, fields, models

REFACING_TARGET_MARGIN = 0.35  # 35% margin target — Build Spec section 6


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    is_refacing_margin_target = fields.Boolean(
        string="Refacing Margin-Target",
        help=(
            "When set, this pricelist item computes its price live to hit "
            "the REFACING_TARGET_MARGIN (35%) over the product's current "
            "standard_price. Used only by pricelist_refacing per "
            "Mapping section 3.2."
        ),
    )

    def _compute_price(self, product, quantity, uom, date, currency=None, **kwargs):
        """Dispatch refacing margin-target items to _compute_refacing_price.

        Odoo's native pricing engine only knows fixed/percentage/formula, so a
        pricelist item carrying the custom live-cost→35%-margin rule would
        otherwise fall through to the base price and the whole Refacing (CTHS)
        channel would silently be a no-op. Intercept BEFORE the native branch,
        but ONLY for items flagged is_refacing_margin_target — every other
        pricelist/channel stays on the stock code path, untouched.
        """
        if self and self.is_refacing_margin_target:
            self.ensure_one()
            return self._compute_refacing_price(product, quantity, date=date)
        return super()._compute_price(
            product, quantity, uom, date, currency=currency, **kwargs)

    def _compute_refacing_price(self, product, quantity, partner=False, date=False):
        """Return price set to hit REFACING_TARGET_MARGIN over cost.

        Formula: price = cost / (1 - margin) so that
        margin = (price - cost) / price = REFACING_TARGET_MARGIN.

        For zero-cost products (rare; usually a seed-data issue),
        returns the product's list_price as a sane fallback.
        """
        self.ensure_one()
        cost = product.standard_price or 0.0
        if cost <= 0.0:
            return product.list_price
        return round(cost / (1.0 - REFACING_TARGET_MARGIN), 2)
