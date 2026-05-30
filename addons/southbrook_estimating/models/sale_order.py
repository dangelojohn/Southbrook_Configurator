# SPDX-License-Identifier: LGPL-3.0-only
"""
sale.order extension — channel-to-pricelist resolution dispatcher.

This file IS custom routine #3 per Build Spec section 4. Adding any
business logic beyond _resolve_channel_pricelist requires PUNCHLIST
justification.

The dispatcher reads partner.channel (and partner.tradesperson_tier
when applicable) and returns the matching pricelist record. Called
from a default-getter on pricelist_id so the user can still manually
override the resolved pricelist post-creation.

NF5 behaviour: when channel=tradesperson and tier is null, returns
the base pricelist_tradesperson (cost+5% floor, no tier discount).
A soft warning is logged (not raised) so order creation isn't
blocked but the operations team is alerted.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _resolve_channel_pricelist(self, partner):
        """Return the product.pricelist matching the partner's channel.

        Custom routine #3 per Build Spec section 4. Dispatch-only — no
        business logic beyond mapping channel -> pricelist xml_id.

        Args:
            partner: a res.partner record.

        Returns:
            A product.pricelist record. Falls back to retail when no
            partner is supplied or the channel is unrecognised.
        """
        if not partner:
            return self.env.ref("southbrook_estimating.pricelist_retail")

        channel = partner.channel or "retail"
        mapping = {
            "retail": "southbrook_estimating.pricelist_retail",
            "dealer": "southbrook_estimating.pricelist_dealer",
            "kd": "southbrook_estimating.pricelist_kd",
            "bigbox": "southbrook_estimating.pricelist_bigbox",
            "refacing": "southbrook_estimating.pricelist_refacing",
        }

        if channel == "tradesperson":
            return self._resolve_tradesperson_pricelist(partner)

        return self.env.ref(
            mapping.get(channel, "southbrook_estimating.pricelist_retail")
        )

    def _resolve_tradesperson_pricelist(self, partner):
        """Pick the right tradesperson tier sub-pricelist (NF5)."""
        tier = partner.tradesperson_tier
        if tier == "1":
            return self.env.ref(
                "southbrook_estimating.pricelist_tradesperson_tier_1"
            )
        if tier == "2":
            return self.env.ref(
                "southbrook_estimating.pricelist_tradesperson_tier_2"
            )
        if tier == "3":
            return self.env.ref(
                "southbrook_estimating.pricelist_tradesperson_tier_3"
            )
        _logger.warning(
            "southbrook: partner %s has channel=tradesperson but no "
            "tradesperson_tier set; falling back to base pricelist "
            "(cost+5%% floor, no tier discount).",
            partner.display_name,
        )
        return self.env.ref(
            "southbrook_estimating.pricelist_tradesperson"
        )

    # Default-getter — on new sale.order, auto-resolve from partner
    # without preventing the user from overriding pricelist_id manually.
    @api.onchange("partner_id")
    def _onchange_partner_id_southbrook_pricelist(self):
        for order in self:
            if not order.partner_id:
                continue
            resolved = order._resolve_channel_pricelist(order.partner_id)
            if resolved:
                order.pricelist_id = resolved.id
