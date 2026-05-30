# [REF] (f) — Tests for the saved-configurations bookmark feature.
#
# Scope:
#   1. action_save_config flips is_saved and stores trimmed/bounded
#      bookmark_name on the session.
#   2. The ir.rule scoping product.config.session to portal-owner
#      reads (portal user A cannot see portal user B's sessions).
#
# The portal HTTP route (/my/configurations) and the JSON-RPC
# bookmark endpoint are exercised in the website module's test
# suite — those tests need the full website_sale stack and live in
# website_product_configurator/tests/test_portal_configurations.py.

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSavedConfig(TransactionCase):
    """Model-level tests: action_save_config + ir.rule for portal scoping."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Session = cls.env["product.config.session"]

        # Create a minimal config-ok template inline so the suite
        # doesn't depend on product_configurator demo data being
        # loaded (some CI matrices install --without-demo).
        cls.product_tmpl = cls.env["product.template"].create(
            {
                "name": "Saved-Config Test Template",
                "config_ok": True,
                "type": "consu",
            }
        )

        # Two portal users for the scoping test. Sharing a single
        # demo company is fine — the rule filters by user_id, not by
        # company.
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        portal_group = cls.env.ref("base.group_portal")
        cls.portal_user_a = Users.create(
            {
                "name": "Portal User A",
                "login": "portal_a_savedcfg@example.com",
                "email": "portal_a_savedcfg@example.com",
                "group_ids": [(6, 0, [portal_group.id])],
            }
        )
        cls.portal_user_b = Users.create(
            {
                "name": "Portal User B",
                "login": "portal_b_savedcfg@example.com",
                "email": "portal_b_savedcfg@example.com",
                "group_ids": [(6, 0, [portal_group.id])],
            }
        )

    def _make_session(self, owner):
        """Create a draft session owned by ``owner`` (res.users)."""
        return self.Session.create(
            {
                "product_tmpl_id": self.product_tmpl.id,
                "user_id": owner.id,
            }
        )

    # --- action_save_config behavior ---------------------------------

    def test_action_save_config_flips_is_saved(self):
        """Calling action_save_config should set is_saved=True."""
        session = self._make_session(self.portal_user_a)
        self.assertFalse(session.is_saved)
        self.assertFalse(session.bookmark_name)

        session.action_save_config(name="Track car spec")

        self.assertTrue(session.is_saved)
        self.assertEqual(session.bookmark_name, "Track car spec")

    def test_action_save_config_trims_whitespace(self):
        """Leading/trailing whitespace on name should be trimmed."""
        session = self._make_session(self.portal_user_a)

        session.action_save_config(name="   Gift for Sam   ")

        self.assertEqual(session.bookmark_name, "Gift for Sam")

    def test_action_save_config_bounds_length(self):
        """Names longer than 128 chars should be clipped (DB-bloat guard)."""
        session = self._make_session(self.portal_user_a)
        long_name = "A" * 500

        session.action_save_config(name=long_name)

        self.assertEqual(len(session.bookmark_name), 128)
        self.assertTrue(session.is_saved)

    def test_action_save_config_blank_name_preserves_existing(self):
        """Passing None/empty leaves existing bookmark_name alone."""
        session = self._make_session(self.portal_user_a)
        session.action_save_config(name="Original")
        self.assertEqual(session.bookmark_name, "Original")

        # Re-save without a name — should not blank out the original.
        session.action_save_config()
        self.assertEqual(session.bookmark_name, "Original")
        self.assertTrue(session.is_saved)

    # --- ir.rule portal scoping --------------------------------------

    def test_portal_user_cannot_read_other_users_session(self):
        """Portal user A must NOT see portal user B's session.

        The ir.rule product_config_session_portal_rule restricts the
        portal-group read to user_id == self.env.user. Without the
        rule, the CSV ACL alone would expose every portal user's
        sessions to every other portal user.

        Note: we test via search(), NOT browse().exists(). Odoo's
        exists() does a raw SQL existence check that bypasses
        ir.rule by design — it only confirms the physical row is
        present. search() (and any read access) applies rules.
        """
        session_b = self._make_session(self.portal_user_b)
        session_b.action_save_config(name="B's private build")

        sessions_visible_to_a = self.Session.with_user(
            self.portal_user_a
        ).search([("id", "=", session_b.id)])
        self.assertFalse(
            sessions_visible_to_a,
            "Portal user A should not be able to read user B's session",
        )

    def test_portal_user_can_read_own_session(self):
        """Portal user A must be able to read their own saved session."""
        session_a = self._make_session(self.portal_user_a)
        session_a.action_save_config(name="A's coupe")

        own_session = self.Session.with_user(self.portal_user_a).search(
            [("id", "=", session_a.id)]
        )
        self.assertTrue(own_session, "Portal user A should read their own session")
        self.assertEqual(own_session.bookmark_name, "A's coupe")

    def test_portal_user_cannot_search_other_users_sessions(self):
        """search() respects the rule — A's search returns only their own."""
        own_session = self._make_session(self.portal_user_a)
        own_session.action_save_config(name="A's build")
        other_session = self._make_session(self.portal_user_b)
        other_session.action_save_config(name="B's build")

        found = self.Session.with_user(self.portal_user_a).search(
            [("is_saved", "=", True)]
        )
        self.assertIn(own_session, found)
        self.assertNotIn(other_session, found)

    def test_internal_user_unaffected_by_portal_rule(self):
        """Internal users (admin et al.) keep their full visibility.

        The rule has groups=[group_portal] only, so the internal
        user's environment never matches the rule's group filter and
        the rule doesn't apply.
        """
        session_a = self._make_session(self.portal_user_a)
        session_b = self._make_session(self.portal_user_b)

        # env defaults to admin; both must be visible.
        self.assertTrue(self.Session.browse(session_a.id).exists())
        self.assertTrue(self.Session.browse(session_b.id).exists())

    def test_portal_user_blocked_from_write_via_acl(self):
        """Portal CSV ACL grants only read — write must fail.

        Belt-and-braces: even if the ir.rule somehow let a portal
        user reach a record, the ACL still denies perm_write=0 for
        base.group_portal on product.config.session.
        """
        session = self._make_session(self.portal_user_a)
        with self.assertRaises(AccessError):
            session.with_user(self.portal_user_a).write(
                {"bookmark_name": "tampered"}
            )
