# SPDX-License-Identifier: LGPL-3.0-only
"""
Extend res.partner with the channel + tradesperson_tier fields.

The channel field is the keystone of southbrook_estimating's pricing
resolution — sale.order.action_confirm reads partner.channel via the
custom routine #3 dispatcher (_resolve_channel_pricelist, lands in commit 4)
to pick the right pricelist.

Per Q5 locked decision: the channel selection uses `tradesperson` as the
technical key (grep-safe), and the workbook vocabulary ("Contractor
Pricing") is preserved as the UI label. The series-vs-channel naming
clash is resolved by keeping `contractor` for the entry-level series
attribute value and `tradesperson` for the cost-plus channel.

Per NF5 locked decision: `tradesperson_tier` is nullable on the model.
`_resolve_channel_pricelist` (commit 4) handles three paths:
  - tier=1 → pricelist_tradesperson_tier_1
  - tier=2 → pricelist_tradesperson_tier_2
  - tier=3 → pricelist_tradesperson_tier_3
  - tier=None → pricelist_tradesperson (base; cost+5% only)
New tradesperson partners default to tier 3 (the entry tier per
the Pricing Evolution tab of #5). Existing untiered partners get a
soft warning at order creation (logged, not blocking).
"""
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # --- Channel (Q1 + Q5 + Q21) ----------------------------------------
    channel = fields.Selection(
        selection=[
            ("retail", "Retail (Walk-in)"),
            ("dealer", "Dealer (−50%)"),
            ("tradesperson", "Contractor Pricing"),
            ("kd", "Central KD"),
            ("bigbox", "Big-Box Wholesale"),
            ("refacing", "Refacing (CTHS)"),
        ],
        string="Southbrook Channel",
        default="retail",
        help=(
            "The sales channel for this partner. Drives pricelist "
            "resolution at sale.order creation via "
            "_resolve_channel_pricelist (custom routine #3). "
            "Workbook label 'Contractor' is preserved as the UI label "
            "for the 'tradesperson' technical key per Q5 — grep-safety "
            "in code, fidelity in UI."
        ),
    )

    # --- Tradesperson tier (NF5) ----------------------------------------
    tradesperson_tier = fields.Selection(
        selection=[
            ("1", "Tier 1 (−25%)"),
            ("2", "Tier 2 (−30%)"),
            ("3", "Tier 3 (−35%)"),
        ],
        string="Tradesperson Tier",
        help=(
            "Only meaningful when channel='tradesperson'. Default for new "
            "tradesperson partners is Tier 3 (the entry tier per the "
            "workbook's Pricing Evolution tab). Tier-determined discount "
            "is applied as a second-stage multiplier on top of the "
            "cost+5% floor; see pricelists.xml."
        ),
    )

    # ------------------------------------------------------------------
    # Defaults: when channel is set to 'tradesperson' and no tier is set,
    # default to '3' per NF5. Apply via onchange so existing records
    # aren't disturbed at install time — only fresh user actions trigger.
    # ------------------------------------------------------------------
    @api.onchange("channel")
    def _onchange_channel_default_tier(self):
        for partner in self:
            if partner.channel == "tradesperson" and not partner.tradesperson_tier:
                partner.tradesperson_tier = "3"
            elif partner.channel != "tradesperson":
                # Tier is meaningless off-channel; clear silently.
                partner.tradesperson_tier = False
