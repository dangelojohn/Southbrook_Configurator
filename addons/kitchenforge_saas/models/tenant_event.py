# SPDX-License-Identifier: LGPL-3.0-only
"""Tenant lifecycle audit log — one row per status transition or webhook."""
from odoo import fields, models


class KitchenForgeTenantEvent(models.Model):
    _name = "kitchenforge.tenant.event"
    _description = "KitchenForge Tenant Lifecycle Event"
    _order = "create_date desc"
    _rec_name = "event_type"

    tenant_id = fields.Many2one(
        "kitchenforge.tenant", required=True,
        ondelete="cascade", index=True)
    event_type = fields.Selection(
        [
            ("created", "Created"),
            ("provision_requested", "Provision Requested"),
            ("provisioned", "Provisioned"),
            ("suspended", "Suspended"),
            ("resumed", "Resumed"),
            ("cancelled", "Cancelled"),
            ("stripe_webhook", "Stripe Webhook"),
            ("seat_added", "Seat Added"),
            ("seat_removed", "Seat Removed"),
            ("usage_recomputed", "Usage Recomputed"),
            ("other", "Other"),
        ],
        required=True, default="other", index=True,
    )
    message = fields.Char(required=True)
    payload_json = fields.Text(
        help="Optional JSON snapshot of the triggering payload "
             "(webhook body, REST request, etc.).")
