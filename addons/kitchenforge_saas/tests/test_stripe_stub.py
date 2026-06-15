# SPDX-License-Identifier: LGPL-3.0-only
"""StripeClient must no-op when no secret key is configured."""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.kitchenforge_saas.models.stripe_client import (
    StripeClient, STRIPE_SECRET_PARAM,
)


@tagged("post_install", "-at_install", "kitchenforge", "saas")
class TestStripeStub(TransactionCase):

    def test_client_disabled_without_secret(self):
        # Ensure no leftover secret from another test/run.
        self.env["ir.config_parameter"].sudo().set_param(
            STRIPE_SECRET_PARAM, "")
        client = StripeClient(self.env)
        self.assertFalse(client.enabled)

    def test_create_subscription_no_op_when_disabled(self):
        self.env["ir.config_parameter"].sudo().set_param(
            STRIPE_SECRET_PARAM, "")
        Tenant = self.env["kitchenforge.tenant"]
        Plan = self.env["kitchenforge.subscription.plan"]
        plan = Plan.search([("code", "=", "direct")], limit=1)
        tenant = Tenant.create({
            "name": "Stub Shop",
            "slug": "stub-shop",
            "admin_email": "owner@stub.example",
            "tier": "direct",
            "billing_provider": "stripe",
        })
        client = StripeClient(self.env)
        result = client.create_subscription(tenant, plan)
        self.assertIsNone(result)
        # No stripe ids written.
        self.assertFalse(tenant.stripe_customer_id)
        self.assertFalse(tenant.stripe_subscription_id)

    def test_cancel_subscription_no_op_when_disabled(self):
        self.env["ir.config_parameter"].sudo().set_param(
            STRIPE_SECRET_PARAM, "")
        tenant = self.env["kitchenforge.tenant"].create({
            "name": "Cancel Stub",
            "slug": "cancel-stub",
            "admin_email": "owner@cancel.example",
            "tier": "direct",
            "billing_provider": "stripe",
            "stripe_subscription_id": "sub_fake",
        })
        client = StripeClient(self.env)
        result = client.cancel_subscription(tenant)
        self.assertIsNone(result)

    def test_provision_does_not_crash_without_stripe(self):
        """Stripe-flavoured provision must still flip status to
        provisioning even when no Stripe credentials are configured."""
        self.env["ir.config_parameter"].sudo().set_param(
            STRIPE_SECRET_PARAM, "")
        tenant = self.env["kitchenforge.tenant"].create({
            "name": "Stripeless Shop",
            "slug": "stripeless",
            "admin_email": "owner@stripeless.example",
            "tier": "direct",
            "billing_provider": "stripe",
        })
        tenant.action_provision()
        self.assertEqual(tenant.status, "provisioning")
