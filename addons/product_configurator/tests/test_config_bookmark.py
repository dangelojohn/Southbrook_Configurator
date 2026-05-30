# Copyright 2026 OdooIQ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Tests for product.config.bookmark — the FEATURE 2 saved-configs
data model that replaces the legacy is_saved + bookmark_name fields
on product.config.session.

What we cover:
  - Field defaults and required constraints
  - Name normalization (trim, length bound)
  - sql_constraint: name cannot be empty/whitespace
  - has_active_bookmark compute on session
  - action_save_config creates a bookmark (and is idempotent)
  - action_touch_viewed bumps last_viewed
  - action_archive/unarchive soft-delete semantics
  - create_from_session factory + cross-user access check
  - ir.rule portal scoping (A cannot see B's bookmarks)
"""

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestConfigBookmark(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Bookmark = cls.env["product.config.bookmark"]
        cls.Session = cls.env["product.config.session"]

        # Minimal config_ok template — keeps tests demo-data-independent.
        cls.product_tmpl = cls.env["product.template"].create(
            {
                "name": "Bookmark Test Template",
                "config_ok": True,
                "type": "consu",
            }
        )

        cls.portal_a = new_test_user(
            cls.env,
            login="bookmark_a@example.com",
            groups="base.group_portal",
            name="Portal A",
        )
        cls.portal_b = new_test_user(
            cls.env,
            login="bookmark_b@example.com",
            groups="base.group_portal",
            name="Portal B",
        )

    def _make_session(self, owner):
        return self.Session.create(
            {
                "product_tmpl_id": self.product_tmpl.id,
                "user_id": owner.id,
            }
        )

    # ------------------------------------------------------------------
    # Field defaults + required
    # ------------------------------------------------------------------

    def test_create_minimal_bookmark(self):
        session = self._make_session(self.portal_a)
        bm = self.Bookmark.create(
            {
                "name": "Track-car spec",
                "session_id": session.id,
                "user_id": self.portal_a.id,
            }
        )
        self.assertTrue(bm.active)
        self.assertTrue(bm.last_viewed)
        self.assertEqual(bm.partner_id, self.portal_a.partner_id)
        self.assertEqual(bm.product_tmpl_id, self.product_tmpl)

    def test_default_user_is_current(self):
        session = self._make_session(self.env.user)
        bm = self.Bookmark.create(
            {"name": "Default-owner test", "session_id": session.id}
        )
        self.assertEqual(bm.user_id, self.env.user)

    # ------------------------------------------------------------------
    # Name normalization + constraint
    # ------------------------------------------------------------------

    def test_name_is_trimmed_on_create(self):
        session = self._make_session(self.portal_a)
        bm = self.Bookmark.create(
            {
                "name": "   Padded label   ",
                "session_id": session.id,
                "user_id": self.portal_a.id,
            }
        )
        self.assertEqual(bm.name, "Padded label")

    def test_name_is_bounded_on_create(self):
        session = self._make_session(self.portal_a)
        long_name = "A" * 500
        bm = self.Bookmark.create(
            {
                "name": long_name,
                "session_id": session.id,
                "user_id": self.portal_a.id,
            }
        )
        self.assertEqual(len(bm.name), 128)

    def test_name_is_trimmed_on_write(self):
        session = self._make_session(self.portal_a)
        bm = self.Bookmark.create(
            {
                "name": "Original",
                "session_id": session.id,
                "user_id": self.portal_a.id,
            }
        )
        bm.write({"name": "  Trimmed via write  "})
        self.assertEqual(bm.name, "Trimmed via write")

    def test_empty_name_rejected_with_friendly_error(self):
        """Whitespace-only names are rejected by the normalizer
        with a UserError (friendlier than the IntegrityError the
        sql_constraint would produce; both gates still in place)."""
        session = self._make_session(self.portal_a)
        with self.assertRaises(UserError):
            self.Bookmark.create(
                {
                    "name": "   ",
                    "session_id": session.id,
                    "user_id": self.portal_a.id,
                }
            )

    # ------------------------------------------------------------------
    # has_active_bookmark compute
    # ------------------------------------------------------------------

    def test_has_active_bookmark_compute(self):
        session = self._make_session(self.portal_a)
        self.assertFalse(session.has_active_bookmark)

        bm = self.Bookmark.create(
            {
                "name": "test",
                "session_id": session.id,
                "user_id": self.portal_a.id,
            }
        )
        session.invalidate_recordset(["has_active_bookmark"])
        self.assertTrue(session.has_active_bookmark)

        bm.action_archive()
        session.invalidate_recordset(["has_active_bookmark"])
        self.assertFalse(session.has_active_bookmark)

    # ------------------------------------------------------------------
    # action_save_config (inherited override)
    # ------------------------------------------------------------------

    def test_action_save_config_creates_bookmark(self):
        session = self._make_session(self.portal_a)
        self.assertFalse(session.bookmark_ids)

        result = session.action_save_config(name="From save action")

        # Legacy fields still set (backwards compat).
        self.assertTrue(session.is_saved)
        self.assertEqual(session.bookmark_name, "From save action")
        # New: bookmark record created.
        self.assertEqual(len(session.bookmark_ids), 1)
        self.assertEqual(session.bookmark_ids.name, "From save action")
        # The override returns the bookmark.
        self.assertEqual(result, session.bookmark_ids)

    def test_action_save_config_is_idempotent(self):
        session = self._make_session(self.portal_a)
        session.action_save_config(name="First")
        first_id = session.bookmark_ids.id

        # Second call should refresh, not duplicate.
        session.action_save_config(name="Renamed via second call")
        self.assertEqual(len(session.bookmark_ids), 1)
        self.assertEqual(session.bookmark_ids.id, first_id)
        self.assertEqual(session.bookmark_ids.name, "Renamed via second call")

    def test_action_save_config_without_name_uses_template_name(self):
        session = self._make_session(self.portal_a)
        session.action_save_config()
        self.assertEqual(
            session.bookmark_ids.name, self.product_tmpl.name
        )

    # ------------------------------------------------------------------
    # action_touch_viewed
    # ------------------------------------------------------------------

    def test_action_touch_viewed_bumps_last_viewed(self):
        session = self._make_session(self.portal_a)
        bm = self.Bookmark.create(
            {
                "name": "Touch test",
                "session_id": session.id,
                "user_id": self.portal_a.id,
            }
        )
        original = bm.last_viewed
        # Force a small delta so the comparison is reliable even with
        # second-resolution timestamps.
        self.env.cr.execute(
            "UPDATE product_config_bookmark SET last_viewed = "
            "last_viewed - INTERVAL '1 hour' WHERE id = %s",
            (bm.id,),
        )
        bm.invalidate_recordset(["last_viewed"])
        before = bm.last_viewed
        bm.action_touch_viewed()
        self.assertGreater(bm.last_viewed, before)

    # ------------------------------------------------------------------
    # archive / unarchive
    # ------------------------------------------------------------------

    def test_archive_hides_from_default_search(self):
        session = self._make_session(self.portal_a)
        bm = self.Bookmark.create(
            {
                "name": "To archive",
                "session_id": session.id,
                "user_id": self.portal_a.id,
            }
        )
        # Active by default.
        self.assertIn(bm, self.Bookmark.search([]))
        bm.action_archive()
        # Default search excludes inactive.
        self.assertNotIn(bm, self.Bookmark.search([]))
        # But active_test=False finds it.
        self.assertIn(
            bm,
            self.Bookmark.with_context(active_test=False).search([]),
        )

    # ------------------------------------------------------------------
    # create_from_session factory
    # ------------------------------------------------------------------

    def test_create_from_session_uses_session_owner(self):
        session = self._make_session(self.portal_a)
        bm = self.Bookmark.with_user(self.portal_a).create_from_session(
            session, name="From factory"
        )
        self.assertEqual(bm.user_id, self.portal_a)
        self.assertEqual(bm.session_id, session)
        self.assertEqual(bm.name, "From factory")

    def test_create_from_session_blocks_cross_user_external(self):
        """A portal user cannot create a bookmark for another portal
        user's session (external user → blocked)."""
        session_b = self._make_session(self.portal_b)
        with self.assertRaises(AccessError):
            self.Bookmark.with_user(self.portal_a).create_from_session(
                session_b, name="A trying to steal B"
            )

    def test_create_from_session_internal_user_may_bookmark_for_customer(self):
        """An internal user (employee) can bookmark on behalf of a
        customer — back-office UX path."""
        session_a = self._make_session(self.portal_a)
        # env.user is admin/internal by default in tests.
        bm = self.Bookmark.create_from_session(session_a, name="Advisor save")
        # Bookmark owned by the session's owner, not the acting employee.
        self.assertEqual(bm.user_id, self.portal_a)

    # ------------------------------------------------------------------
    # ir.rule portal scoping
    # ------------------------------------------------------------------

    def test_portal_user_cannot_search_other_users_bookmarks(self):
        session_b = self._make_session(self.portal_b)
        bm_b = self.Bookmark.create(
            {
                "name": "B's private",
                "session_id": session_b.id,
                "user_id": self.portal_b.id,
            }
        )
        found_by_a = self.Bookmark.with_user(self.portal_a).search(
            [("id", "=", bm_b.id)]
        )
        self.assertFalse(found_by_a, "Portal A must not see B's bookmark")

    def test_portal_user_can_write_own_bookmarks(self):
        session = self._make_session(self.portal_a)
        bm = (
            self.Bookmark.with_user(self.portal_a)
            .sudo()  # bypass rule for setup
            .create(
                {
                    "name": "Own",
                    "session_id": session.id,
                    "user_id": self.portal_a.id,
                }
            )
        )
        # Now do the actual test write WITHOUT sudo
        bm.with_user(self.portal_a).write({"name": "Renamed by owner"})
        self.assertEqual(bm.name, "Renamed by owner")

    def test_portal_user_cannot_write_other_users_bookmarks(self):
        """A write on a bookmark owned by another portal user is
        blocked by the ir.rule. We assert the operation either
        raises AccessError OR returns without touching the record
        (depending on whether the ORM short-circuits at search or at
        write); either way the value must not change."""
        session_b = self._make_session(self.portal_b)
        bm_b = self.Bookmark.create(
            {
                "name": "B's protected",
                "session_id": session_b.id,
                "user_id": self.portal_b.id,
            }
        )
        original_name = bm_b.name
        raised = False
        try:
            bm_b.with_user(self.portal_a).write({"name": "Hack attempt"})
        except AccessError:
            raised = True
        # Refresh and verify the name was not changed by the attempted
        # cross-user write (whether AccessError fired or the ORM
        # silently filtered the recordset to empty).
        bm_b.invalidate_recordset(["name"])
        self.assertEqual(bm_b.name, original_name)
        # Strongly prefer the AccessError path; log if Odoo took the
        # silent-filter path so we know the rule is working but via
        # a different mechanism.
        if not raised:
            self.assertEqual(bm_b.name, original_name)
