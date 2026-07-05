# SPDX-License-Identifier: LGPL-3.0-only
"""sale.order extension — one CRM follow-up lead per order for the AI
photo-capture flow.

A serious customer photographing their kitchen is a strong buying
signal, so a trustworthy capture creates a crm.lead so a live Southbrook
designer can follow up about their quote. This M2O makes that creation
idempotent per order: the analyze-photos controller updates the SAME
lead on a re-capture rather than spawning duplicates.
"""
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sb_room_capture_lead_id = fields.Many2one(
        "crm.lead",
        string="AI Photo-Capture Follow-up Lead",
        ondelete="set null",
        copy=False,
        help="The CRM lead created when this order's room was captured "
             "from photos, so a designer can follow up. One per order.",
    )
