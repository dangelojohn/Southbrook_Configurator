# [REF] (f) — HTTP tests for /my/configurations + the JSON-RPC
# save endpoint.
#
# These tests need the full website_sale stack (HTTP layer, routing,
# session middleware), so they live here rather than in
# product_configurator/tests/. The model-level tests for
# action_save_config and the ir.rule live in
# product_configurator/tests/test_saved_config.py.
#
# What we cover:
#   - GET /my/configurations renders the list template
#   - The list shows only the logged-in user's saved configs
#   - The "My Configurations" card appears on /my (counter card)
#   - POST /website_product_configurator/save_configuration_bookmark
#     flips is_saved and stores the name
#   - The save endpoint rejects sessions the caller doesn't own
#     (returns 'session not found' — the same shape as missing,
#     to avoid leaking existence)

import json

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestPortalConfigurations(HttpCase):
    """HTTP tests for the saved-configurations portal surface."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Inline a minimal config-ok template (see test_saved_config.py
        # for the same rationale — independence from demo data).
        cls.product_tmpl = cls.env["product.template"].create(
            {
                "name": "Portal-Saved-Config Test Template",
                "config_ok": True,
                "type": "consu",
            }
        )

        # Two portal users. new_test_user gives us a usable
        # login/password pair so we can authenticate the HTTP client.
        cls.portal_a = new_test_user(
            cls.env,
            login="portal_a_cfg@example.com",
            groups="base.group_portal",
            name="Portal A",
        )
        cls.portal_b = new_test_user(
            cls.env,
            login="portal_b_cfg@example.com",
            groups="base.group_portal",
            name="Portal B",
        )

        # Test bookmark names: avoid apostrophes and other HTML-
        # special characters. QWeb's t-out HTML-encodes apostrophes
        # to &#39;, so a literal substring assertion against
        # response.text would miss them. The encoding is correct
        # behavior — we just need test names that round-trip
        # cleanly.
        Session = cls.env["product.config.session"]
        cls.session_a = Session.create(
            {
                "product_tmpl_id": cls.product_tmpl.id,
                "user_id": cls.portal_a.id,
            }
        )
        cls.name_a = "A Sport Line build"
        # FEATURE 2: action_save_config now returns the bookmark
        # record (instead of True). Capture it for routes that
        # expect bookmark_id in the URL.
        cls.bookmark_a = cls.session_a.action_save_config(name=cls.name_a)

        cls.session_b = Session.create(
            {
                "product_tmpl_id": cls.product_tmpl.id,
                "user_id": cls.portal_b.id,
            }
        )
        cls.name_b = "B Diesel build"
        cls.bookmark_b = cls.session_b.action_save_config(name=cls.name_b)

        # Unsaved draft for A — must NOT appear in the list.
        cls.draft_a = Session.create(
            {
                "product_tmpl_id": cls.product_tmpl.id,
                "user_id": cls.portal_a.id,
            }
        )

    # --- GET /my/configurations --------------------------------------

    def test_portal_user_a_lists_only_own_saved_configs(self):
        """A's /my/configurations page shows A's bookmark but not B's."""
        self.authenticate("portal_a_cfg@example.com", "portal_a_cfg@example.com")
        response = self.url_open("/my/configurations")

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn(self.name_a, body, "A should see their own bookmark")
        self.assertNotIn(self.name_b, body, "A must NOT see B's bookmark")

    def test_portal_excludes_unsaved_drafts(self):
        """Draft (is_saved=False) sessions must not appear in the list."""
        self.authenticate("portal_a_cfg@example.com", "portal_a_cfg@example.com")
        response = self.url_open("/my/configurations")

        self.assertEqual(response.status_code, 200)
        # The empty-state message appears only when there are zero
        # saved configs — should NOT appear since A has one saved.
        # And the draft's id (which has no bookmark_name) shouldn't
        # render as a row.
        self.assertIn(self.name_a, response.text)
        self.assertNotIn("Unnamed configuration", response.text)

    def test_empty_state_when_no_saved_configs(self):
        """A buyer with zero saved configs sees the empty-state hint."""
        empty_user = new_test_user(
            self.env,
            login="empty_cfg@example.com",
            groups="base.group_portal",
            name="Empty User",
        )
        self.authenticate(empty_user.login, empty_user.login)
        response = self.url_open("/my/configurations")

        self.assertEqual(response.status_code, 200)
        # QWeb renders the literal apostrophe in this template
        # context (no HTML escaping of t-out content here); assert
        # against the raw text.
        self.assertIn(
            "don't have any saved configurations",
            response.text,
            "Empty-state hint should render",
        )

    # --- Resume route -----------------------------------------------

    def test_resume_redirects_to_shop_product(self):
        """Resuming a saved config redirects to /shop/product/<slug>.

        FEATURE 2: the resume URL now takes a bookmark_id (the
        buyer-facing entity), not a session_id.
        """
        self.authenticate("portal_a_cfg@example.com", "portal_a_cfg@example.com")
        response = self.url_open(
            f"/my/configurations/{self.bookmark_a.id}/resume",
            allow_redirects=False,
        )
        # 303/302 redirect expected
        self.assertIn(response.status_code, (302, 303))
        self.assertIn("/shop/product/", response.headers.get("Location", ""))

    def test_resume_404s_other_users_bookmark(self):
        """A attempting to resume B's bookmark redirects back to the list."""
        self.authenticate("portal_a_cfg@example.com", "portal_a_cfg@example.com")
        response = self.url_open(
            f"/my/configurations/{self.bookmark_b.id}/resume",
            allow_redirects=False,
        )
        self.assertIn(response.status_code, (302, 303))
        # The "not yours / not found" path lands on the list page.
        self.assertIn(
            "/my/configurations",
            response.headers.get("Location", ""),
        )

    # --- JSON-RPC save endpoint --------------------------------------

    def _jsonrpc(self, route, params):
        """Helper: POST a JSON-RPC call against the in-process server."""
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": params,
        }
        return self.url_open(
            route,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_save_bookmark_endpoint_flips_is_saved(self):
        """The JSON-RPC endpoint marks a fresh draft as a bookmark."""
        Session = self.env["product.config.session"]
        fresh = Session.create(
            {
                "product_tmpl_id": self.product_tmpl.id,
                "user_id": self.portal_a.id,
            }
        )
        self.assertFalse(fresh.is_saved)

        self.authenticate("portal_a_cfg@example.com", "portal_a_cfg@example.com")
        response = self._jsonrpc(
            "/website_product_configurator/save_configuration_bookmark",
            {"session_id": fresh.id, "name": "Endpoint test"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["result"]["ok"], body)
        self.assertEqual(body["result"]["name"], "Endpoint test")

        fresh.invalidate_recordset()
        self.assertTrue(fresh.is_saved)
        self.assertEqual(fresh.bookmark_name, "Endpoint test")

    def test_save_bookmark_endpoint_rejects_other_users_session(self):
        """A calling save on B's session must get a clean 'not found'.

        The ir.rule filters out the session row before the controller
        body runs (browse().exists() returns empty), so we report
        'session not found' rather than 'access denied' — avoids
        leaking the fact that the id exists.
        """
        self.authenticate("portal_a_cfg@example.com", "portal_a_cfg@example.com")
        response = self._jsonrpc(
            "/website_product_configurator/save_configuration_bookmark",
            {"session_id": self.session_b.id, "name": "should not work"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["result"]["ok"])
        self.assertEqual(body["result"]["error"], "session not found")

    def test_save_bookmark_endpoint_rejects_invalid_session_id(self):
        """Non-integer session_id should be rejected without 500ing."""
        self.authenticate("portal_a_cfg@example.com", "portal_a_cfg@example.com")
        response = self._jsonrpc(
            "/website_product_configurator/save_configuration_bookmark",
            {"session_id": "not-a-number", "name": "x"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["result"]["ok"])
        self.assertEqual(body["result"]["error"], "invalid session_id")
