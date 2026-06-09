# SPDX-License-Identifier: LGPL-3.0-only
"""Portal ACL boundary tests — must be tested as an anonymous SECOND
customer per init-doc 'ACL testing discipline'. Admin-as-second-customer
would surface false positives because admin bypasses ir.rule."""
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "customer_portal", "acl")
class TestPortalACL(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        Users = cls.env["res.users"]
        portal_group = cls.env.ref("base.group_portal")

        cls.alice_partner = Partner.create({
            "name": "Alice Customer", "email": "alice.acl@example.com",
        })
        cls.alice_user = Users.create({
            "login": "alice.acl@example.com",
            "password": "alice-password-strong",
            "partner_id": cls.alice_partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })
        cls.bob_partner = Partner.create({
            "name": "Bob Customer", "email": "bob.acl@example.com",
        })
        cls.bob_user = Users.create({
            "login": "bob.acl@example.com",
            "password": "bob-password-strong",
            "partner_id": cls.bob_partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })

        Project = cls.env["sb.kitchen.project"]
        cls.alice_project = Project.create({
            "name": "Alice Kitchen",
            "partner_id": cls.alice_partner.id,
            "theme": "signature",
        })
        cls.bob_project = Project.create({
            "name": "Bob Kitchen",
            "partner_id": cls.bob_partner.id,
            "theme": "contractor",
        })

    def test_alice_can_see_her_own_project(self):
        self.authenticate("alice.acl@example.com", "alice-password-strong")
        resp = self.url_open(f"/my/kitchen-project/{self.alice_project.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Alice Kitchen", resp.text)

    def test_alice_cannot_see_bobs_project(self):
        """The critical test — same surface as 'project not found' for
        no-such-project, so the controller does not leak existence."""
        self.authenticate("alice.acl@example.com", "alice-password-strong")
        resp = self.url_open(f"/my/kitchen-project/{self.bob_project.id}")
        # Could be 404 OR a portal-style 'not found' page. Either way:
        # MUST NOT contain Bob's project name.
        self.assertNotIn("Bob Kitchen", resp.text,
                          "Alice must NEVER see Bob's project name")

    def test_alice_sees_only_her_own_in_the_list(self):
        self.authenticate("alice.acl@example.com", "alice-password-strong")
        resp = self.url_open("/my/kitchen-projects")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Alice Kitchen", resp.text)
        self.assertNotIn("Bob Kitchen", resp.text)

    def test_anonymous_user_redirected_or_blocked(self):
        """No portal session at all."""
        # No authenticate() — request is anonymous.
        resp = self.url_open(
            f"/my/kitchen-project/{self.alice_project.id}",
            allow_redirects=False,
        )
        # auth='user' redirects to /web/login (3xx).
        self.assertIn(resp.status_code, (301, 302, 303, 401, 403))
