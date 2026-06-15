# SPDX-License-Identifier: LGPL-3.0-only
"""Stripe integration stub.

A thin wrapper around the official `stripe` Python SDK. By design this
module degrades gracefully:

* If `stripe` isn't importable, every method is a logged no-op.
* If `ir.config_parameter` `kitchenforge_saas.stripe_secret_key` isn't
  set, every method is a logged no-op.

This keeps the unit tests offline-safe and makes the control plane
installable on Odoo deployments without Stripe credentials yet.
"""
import logging

_logger = logging.getLogger(__name__)

STRIPE_SECRET_PARAM = "kitchenforge_saas.stripe_secret_key"
STRIPE_WEBHOOK_SECRET_PARAM = "kitchenforge_saas.stripe_webhook_secret"


def _try_import_stripe():
    """Return the `stripe` module or None. Logged once."""
    try:
        import stripe  # type: ignore  # noqa: F401
        return stripe
    except ImportError:
        _logger.info(
            "stripe package not importable; StripeClient is a no-op. "
            "pip install stripe to enable real billing.")
        return None


class StripeClient:
    """Lazy-init Stripe client. Constructed per call site; cheap."""

    def __init__(self, env):
        self.env = env
        self._stripe = _try_import_stripe()
        if self._stripe is not None:
            secret = env["ir.config_parameter"].sudo().get_param(
                STRIPE_SECRET_PARAM, "")
            if not secret:
                _logger.warning(
                    "%s not set in ir.config_parameter; StripeClient "
                    "calls will no-op.", STRIPE_SECRET_PARAM)
                self._stripe = None
            else:
                self._stripe.api_key = secret

    @property
    def enabled(self):
        return self._stripe is not None

    # ------------------------------------------------------------------
    # Public surface — methods callable from tenant lifecycle actions.
    # ------------------------------------------------------------------
    def create_subscription(self, tenant, plan):
        """Create-or-attach a Stripe subscription for a tenant.

        Returns the subscription id on success, None on no-op or failure.
        Writes the resulting ids back onto the tenant record.
        """
        if not self.enabled:
            _logger.info(
                "stripe no-op: create_subscription(%s, %s)",
                tenant.slug, plan.code)
            return None
        try:
            customer_id = tenant.stripe_customer_id
            if not customer_id:
                customer = self._stripe.Customer.create(
                    email=tenant.admin_email,
                    name=tenant.name,
                    metadata={
                        "kitchenforge_tenant_id": str(tenant.id),
                        "kitchenforge_slug": tenant.slug,
                    },
                )
                customer_id = customer.id
                tenant.sudo().write({"stripe_customer_id": customer_id})
            # Pricing: use the plan code as the Stripe Price lookup_key.
            # In real Stripe accounts the operator creates the Price
            # objects with matching lookup_keys ahead of time.
            sub = self._stripe.Subscription.create(
                customer=customer_id,
                items=[{"price_data": None,
                        "price_lookup_key": plan.code}],
                metadata={
                    "kitchenforge_tenant_id": str(tenant.id),
                    "plan_code": plan.code,
                },
            )
            tenant.sudo().write({"stripe_subscription_id": sub.id})
            return sub.id
        except Exception as exc:  # noqa: BLE001 — log + downgrade
            _logger.warning(
                "stripe create_subscription failed for %s: %s",
                tenant.slug, exc)
            return None

    def cancel_subscription(self, tenant):
        """Cancel a tenant's Stripe subscription. Idempotent."""
        if not self.enabled:
            _logger.info("stripe no-op: cancel_subscription(%s)", tenant.slug)
            return None
        if not tenant.stripe_subscription_id:
            return None
        try:
            self._stripe.Subscription.delete(tenant.stripe_subscription_id)
            return True
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "stripe cancel_subscription failed for %s: %s",
                tenant.slug, exc)
            return False

    def verify_webhook(self, body, signature):
        """Verify an incoming Stripe webhook signature.

        Returns the parsed event dict on success, None on failure or
        no-op. Caller is responsible for acting on the event type.
        """
        if not self.enabled:
            _logger.info("stripe no-op: verify_webhook")
            return None
        secret = self.env["ir.config_parameter"].sudo().get_param(
            STRIPE_WEBHOOK_SECRET_PARAM, "")
        if not secret:
            _logger.warning(
                "%s not set; cannot verify webhook signature.",
                STRIPE_WEBHOOK_SECRET_PARAM)
            return None
        try:
            return self._stripe.Webhook.construct_event(
                body, signature, secret)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("stripe webhook verify failed: %s", exc)
            return None
