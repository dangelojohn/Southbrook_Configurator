# SPDX-License-Identifier: LGPL-3.0-only
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "southbrook", "customer_portal", "fabio")
class TestFabioPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal_group = cls.env.ref("base.group_portal")
        cls.partner = cls.env["res.partner"].create({
            "name": "Fabio Portal Customer",
            "email": "fabio.portal@example.com",
        })
        cls.user = cls.env["res.users"].create({
            "login": "fabio.portal@example.com",
            "password": "fabio-portal-password",
            "partner_id": cls.partner.id,
            "group_ids": [(6, 0, [portal_group.id])],
        })
        cls.other_partner = cls.env["res.partner"].create({
            "name": "Fabio Other Customer",
            "email": "fabio.other@example.com",
        })
        cls.project = cls.env["sb.kitchen.project"].create({
            "name": "Fabio Customer Kitchen",
            "partner_id": cls.partner.id,
            "state": "awaiting_customer",
        })
        cls.other_project = cls.env["sb.kitchen.project"].create({
            "name": "Private Other Kitchen",
            "partner_id": cls.other_partner.id,
            "state": "in_production",
        })

    def test_portal_fabio_page_loads_for_customer(self):
        self.authenticate("fabio.portal@example.com", "fabio-portal-password")

        resp = self.url_open("/my/fabio")

        self.assertEqual(resp.status_code, 200)
        self.assertIn("Ask Fabio", resp.text)
        self.assertIn("Fabio Customer Kitchen", resp.text)
        self.assertNotIn("Private Other Kitchen", resp.text)

    def test_customer_fabio_answer_is_scoped_to_customer_project(self):
        question = self.env["southbrook.hermes.question"].ask_customer(
            self.partner,
            "What is the status of my kitchen?",
            project=self.project,
            user=self.user,
        )

        self.assertIn("Fabio Customer Kitchen", question.answer)
        self.assertNotIn("Private Other Kitchen", question.answer)

    def test_customer_cannot_ask_about_another_customer_project(self):
        with self.assertRaises(UserError):
            self.env["southbrook.hermes.question"].ask_customer(
                self.partner,
                "What is the status of that kitchen?",
                project=self.other_project,
                user=self.user,
            )
