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

    # ------------------------------------------------------------------
    # Analytics capture (NF1 — Build Spec section 8 "AI data spine")
    # ------------------------------------------------------------------
    # Fire the southbrook.order.analytics.capture() hook at confirm-time.
    # Idempotent; safe to re-confirm. NF1 carve-out: this is data capture,
    # not business logic — does not bump the 7-routine custom register.
    def action_confirm(self):
        result = super().action_confirm()
        Analytics = self.env["southbrook.order.analytics"]
        for order in self:
            Analytics.capture(order)
        return result

    # ------------------------------------------------------------------
    # NF6 — Image Floor iterative-design pattern (Case Study section 3.A)
    # ------------------------------------------------------------------
    # parent_order_id + version + action_duplicate_as_draft give reps
    # the "Duplicate as Draft" affordance that Image Floor's 3-visit flow
    # needs: same kitchen revised 3 times, each saved as a new draft with
    # the prior version linked. Free side-effect: full revision history
    # walkable via parent_order_id chain.
    #
    # Schema only. The view button + action wiring lands in
    # views/sale_order_views.xml.
    parent_order_id = fields.Many2one(
        "sale.order",
        string="Parent Order (Duplicated From)",
        ondelete="set null",
        copy=False,
        help=(
            "When this order was created via 'Duplicate as Draft', this "
            "Many2one points at the prior version. NF6 — Image Floor "
            "iterative-design pattern."
        ),
    )
    version = fields.Integer(
        string="Version",
        default=1,
        copy=False,
        help=(
            "Auto-incremented by action_duplicate_as_draft. The Image "
            "Floor flow typically reaches v3 before final confirmation."
        ),
    )

    def action_duplicate_as_draft(self):
        """Create a new draft sale.order copied from this one (NF6).

        Copies all order lines (preserving product.config.session refs
        where applicable), links parent_order_id, increments version,
        stays in draft state ('draft' / 'sent'). Safe to chain — v3
        duplicates v2 which duplicates v1.

        Returns the action descriptor that opens the new order's form.
        """
        self.ensure_one()
        new_order = self.copy({
            "parent_order_id": self.id,
            "version": self.version + 1,
            "state": "draft",
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": new_order.id,
            "view_mode": "form",
            "target": "current",
            "name": f"{new_order.name} (v{new_order.version})",
        }
