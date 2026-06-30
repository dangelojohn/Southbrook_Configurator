# addons/southbrook_os/tests/test_os_revision.py
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "southbrook_os")
class TestOsRevision(TransactionCase):
    def setUp(self):
        super().setUp()
        # NOTE: post_init_hook `_post_init_load_canonical` pre-seeds slug
        # `04_lifecycle`. Tests use a `99_test_*` prefix to avoid colliding
        # with the unique-slug constraint on canonical seeds.
        self.section = self.env["southbrook.os.section"].create({
            "slug": "99_test_lifecycle", "name": "Lifecycle",
            "source": "canonical", "body": "v1 body",
        })

    def test_full_state_machine_draft_to_applied(self):
        Rev = self.env["southbrook.os.revision"]
        rev = Rev.create({
            "target_slug": "99_test_lifecycle",
            "change_summary": "Add Tier 4 partner pricing note",
            "proposed_body": "v2 body",
        })
        self.assertEqual(rev.state, "draft")
        rev.action_submit_for_review()
        self.assertEqual(rev.state, "review")
        rev.action_approve()
        self.assertEqual(rev.state, "approved")
        rev.action_apply()
        self.assertEqual(rev.state, "applied")
        # The section now carries the new body at version 2
        self.section.invalidate_recordset()
        self.assertEqual(self.section.body, "v2 body")
        self.assertEqual(self.section.version, 2)

    def test_cannot_apply_unapproved_osro(self):
        rev = self.env["southbrook.os.revision"].create({
            "target_slug": "99_test_lifecycle",
            "change_summary": "X",
            "proposed_body": "X",
        })
        with self.assertRaises(UserError):
            rev.action_apply()

    def test_cannot_target_missing_slug(self):
        rev = self.env["southbrook.os.revision"].create({
            "target_slug": "no_such_slug",
            "change_summary": "X",
            "proposed_body": "X",
        })
        rev.action_submit_for_review()
        rev.action_approve()
        with self.assertRaises(UserError):
            rev.action_apply()

    def test_reject_from_review(self):
        rev = self.env["southbrook.os.revision"].create({
            "target_slug": "99_test_lifecycle",
            "change_summary": "Bad idea",
            "proposed_body": "X",
        })
        rev.action_submit_for_review()
        rev.action_reject()
        self.assertEqual(rev.state, "rejected")
