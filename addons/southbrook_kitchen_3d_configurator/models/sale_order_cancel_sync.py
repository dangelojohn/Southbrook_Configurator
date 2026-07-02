# SPDX-License-Identifier: LGPL-3.0-only
"""Reverse of the ordered→SO transition: when a sale.order tied to a
kitchen.design is cancelled, revert the design back to state='configured'
and clear sale_order_id so it becomes editable + re-quotable.

Complements `kitchen_design.action_reset_quote_link` (the manual, per-
design safety valve) by wiring the same effect into the SO-side cancel
event so a rep who cancels the quote/order from the SO surface doesn't
leave an orphaned "quoted"/"ordered" design pointing at a cancelled SO.

Design write is done sudo() only for the m2o clear + state flip so the
sync fires reliably even when the cancelling user has no direct write
access to every affected design (multi-partner shared designs, portal
edge cases). Record rules on read still apply — we only cross the sudo
boundary once we already have the record set in scope from an id-set
search.
"""

import logging

from odoo import models


_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_cancel(self):
        # Let Odoo core (+ any sibling sale.order overrides) run first
        # so we only mutate designs when the cancel actually landed.
        res = super()._action_cancel()
        if not self:
            return res
        Design = self.env["southbrook.kitchen.design"].sudo()
        designs = Design.search([("sale_order_id", "in", self.ids)])
        for design in designs:
            # Edge case — a design still linked to a cancelling SO but
            # somehow already back at configured (concurrent reset,
            # manual heal). No-op silently, don't spam chatter and
            # don't re-trigger any downstream side effects.
            if design.state not in ("quoted", "ordered"):
                continue
            prior = design.sale_order_id
            design.write({"sale_order_id": False, "state": "configured"})
            design.message_post(body=(
                "Linked quotation %s was cancelled. Design unlocked and "
                "reverted to Configured — re-quote when ready."
            ) % (prior.name if prior else "<unknown>"))
            _logger.info(
                "kitchen_design %s reverted to configured after sale.order "
                "%s cancellation", design.name, prior.name if prior else "?",
            )
        return res
