# SPDX-License-Identifier: LGPL-3.0-only
"""Tenant create + lifecycle transitions."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "kitchenforge", "saas")
class TestTenantLifecycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tenant = cls.env["kitchenforge.tenant"]
        cls.Plan = cls.env["kitchenforge.subscription.plan"]

    def _make_tenant(self, slug="acme-cabinetry", **overrides):
        vals = {
            "name": "Acme Cabinetry",
            "slug": slug,
            "admin_email": "owner@acme.example",
            "tier": "direct",
        }
        vals.update(overrides)
        return self.Tenant.create(vals)

    def test_seed_plans_present(self):
        codes = set(self.Plan.search([]).mapped("code"))
        self.assertIn("marathon_channel", codes)
        self.assertIn("direct", codes)
        self.assertIn("enterprise", codes)

    def test_create_tenant_resolves_plan_from_tier(self):
        t = self._make_tenant(slug="resolves-plan", tier="enterprise")
        self.assertEqual(t.status, "pending")
        self.assertEqual(t.plan_id.code, "enterprise")
        self.assertAlmostEqual(t.mrr_usd, 2500.0)
        self.assertTrue(t.created_at)

    def test_slug_must_be_kebab_case(self):
        with self.assertRaises(ValidationError):
            self._make_tenant(slug="Has Spaces")
        with self.assertRaises(ValidationError):
            self._make_tenant(slug="-leading-hyphen")
        with self.assertRaises(ValidationError):
            self._make_tenant(slug="UPPER")

    def test_slug_uniqueness(self):
        self._make_tenant(slug="duplicate-slug")
        with self.assertRaises(Exception):
            self._make_tenant(slug="duplicate-slug")

    def test_admin_email_validation(self):
        with self.assertRaises(ValidationError):
            self._make_tenant(slug="bad-email", admin_email="no-at-sign")

    def test_create_logs_event(self):
        t = self._make_tenant(slug="audited")
        self.assertTrue(any(
            e.event_type == "created" for e in t.event_ids))

    def test_lifecycle_provision_suspend_resume_cancel(self):
        t = self._make_tenant(slug="lifecycle", billing_provider="manual")
        # pending -> provisioning
        t.action_provision()
        self.assertEqual(t.status, "provisioning")
        # provisioner callback -> live
        t.mark_provisioned(docker_compose_path="/tmp/dc.yml")
        self.assertEqual(t.status, "live")
        self.assertEqual(t.docker_compose_path, "/tmp/dc.yml")
        self.assertTrue(t.provisioned_at)
        # live -> suspended
        t.action_suspend()
        self.assertEqual(t.status, "suspended")
        self.assertTrue(t.suspended_at)
        # suspended -> live
        t.action_resume()
        self.assertEqual(t.status, "live")
        self.assertFalse(t.suspended_at)
        # live -> cancelled
        t.action_cancel()
        self.assertEqual(t.status, "cancelled")
        self.assertTrue(t.cancelled_at)
        # cancelled is terminal — re-provision blocked
        with self.assertRaises(UserError):
            t.action_provision()

    def test_cannot_suspend_pending(self):
        t = self._make_tenant(slug="suspend-pending")
        with self.assertRaises(UserError):
            t.action_suspend()

    def test_cannot_resume_live(self):
        t = self._make_tenant(slug="resume-live", billing_provider="manual")
        t.action_provision()
        t.mark_provisioned()
        with self.assertRaises(UserError):
            t.action_resume()

    def test_cron_recompute_usage_runs(self):
        # Just smoke-test: no live tenants -> no error; one live tenant
        # with no partner_id or admin_user_id -> skipped cleanly.
        t = self._make_tenant(slug="cron-smoke", billing_provider="manual")
        t.action_provision()
        t.mark_provisioned()
        # No partner_id, no admin_user_id; should leave value at default.
        self.Tenant.cron_recompute_usage()
        self.assertEqual(t.cabinets_last_30d, 0)

    def test_marathon_referred_flag_round_trips(self):
        t = self._make_tenant(
            slug="marathon-shop",
            tier="marathon_channel",
            marathon_referred=True)
        self.assertTrue(t.marathon_referred)
        self.assertEqual(t.plan_id.code, "marathon_channel")
        self.assertTrue(t.plan_id.marathon_rebate_eligible)
