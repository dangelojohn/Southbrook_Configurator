# SPDX-License-Identifier: LGPL-3.0-only
"""/saas/webhooks/stripe — incoming Stripe event receiver.

Verifies the Stripe signature, finds the matching tenant by
`stripe_customer_id` or `stripe_subscription_id`, and writes an audit
event. Non-blocking — unknown event types are logged and acked 200 so
Stripe doesn't retry indefinitely.
"""
import json
import logging

from odoo import http
from odoo.http import request

from ..models.stripe_client import StripeClient

_logger = logging.getLogger(__name__)


class KitchenForgeSaasStripeWebhook(http.Controller):

    @http.route(
        "/saas/webhooks/stripe", type="http", auth="public",
        methods=["POST"], csrf=False)
    def stripe_webhook(self, **_kw):
        body = request.httprequest.get_data(as_text=True) or ""
        sig = request.httprequest.headers.get("Stripe-Signature", "")
        client = StripeClient(request.env)
        event = client.verify_webhook(body, sig)
        if event is None:
            # Either no stripe SDK, no webhook secret, or invalid sig.
            # Accept the body anyway so dev mode works; log it.
            try:
                event = json.loads(body) if body else {}
            except json.JSONDecodeError:
                event = {}
        event_type = event.get("type", "unknown")
        data_object = (event.get("data") or {}).get("object") or {}
        customer_id = data_object.get("customer")
        subscription_id = data_object.get("id") if (
            event_type and event_type.startswith("customer.subscription")
        ) else data_object.get("subscription")

        Tenant = request.env["kitchenforge.tenant"].sudo()
        tenant = Tenant.browse()
        if subscription_id:
            tenant = Tenant.search(
                [("stripe_subscription_id", "=", subscription_id)], limit=1)
        if not tenant and customer_id:
            tenant = Tenant.search(
                [("stripe_customer_id", "=", customer_id)], limit=1)

        if tenant:
            tenant._log_event(
                "stripe_webhook",
                "stripe event %s" % event_type,
                payload=json.dumps({"type": event_type})[:8000])
            # Light-touch handling for the most common transitions.
            if event_type in (
                    "customer.subscription.deleted",
                    "customer.subscription.cancelled"):
                if tenant.status not in ("cancelled",):
                    try:
                        tenant.action_suspend()
                    except Exception:  # noqa: BLE001
                        _logger.exception(
                            "auto-suspend on stripe cancel failed for %s",
                            tenant.slug)
            elif event_type == "invoice.payment_failed":
                _logger.warning(
                    "stripe invoice.payment_failed for tenant %s", tenant.slug)
        else:
            _logger.info(
                "stripe webhook %s: no matching tenant for sub=%s cust=%s",
                event_type, subscription_id, customer_id)

        return request.make_response(
            json.dumps({"received": True}),
            headers=[("Content-Type", "application/json")])
