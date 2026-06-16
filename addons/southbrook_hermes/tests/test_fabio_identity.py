# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes", "fabio_identity")
class TestFabioIdentity(TransactionCase):

    def test_fabio_partner_exists_as_contact_not_user(self):
        partner = self.env.ref("southbrook_hermes.partner_fabio_agent")

        self.assertEqual(partner.name, "Fabio")
        self.assertEqual(partner.company_type, "person")
        self.assertFalse(
            self.env["res.users"].sudo().search([
                ("partner_id", "=", partner.id),
            ], limit=1),
            "Fabio should be a contact identity, not a login user.",
        )

    def test_recommendation_defaults_to_fabio_agent_partner(self):
        partner = self.env.ref("southbrook_hermes.partner_fabio_agent")

        rec = self.env["southbrook.hermes.recommendation"].create({
            "name": "Fabio source identity",
            "summary": "This recommendation should show Fabio as its agent.",
            "payload_json": "{}",
        })

        self.assertEqual(rec.agent_partner_id, partner)

    def test_views_show_fabio_agent_field_with_avatar_widget(self):
        list_view = self.env.ref("southbrook_hermes.view_hermes_recommendation_list")
        form_view = self.env.ref("southbrook_hermes.view_hermes_recommendation_form")

        self.assertIn('name="agent_partner_id"', list_view.arch_db)
        self.assertIn('name="agent_partner_id"', form_view.arch_db)
        self.assertIn('widget="many2one_avatar"', list_view.arch_db)
        self.assertIn('widget="many2one_avatar"', form_view.arch_db)


@tagged("post_install", "-at_install", "southbrook", "hermes", "fabio_identity")
class TestFabioIdentityApi(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        issued = cls.env["southbrook.api.key"].sudo().issue_for_user(
            cls.env.ref("base.user_admin"), label="fabio-identity-test",
        )
        cls.api_key = issued["cleartext"]

    def test_api_created_recommendation_defaults_to_fabio_agent_partner(self):
        partner = self.env.ref("southbrook_hermes.partner_fabio_agent")

        resp = self.url_open(
            "/hermes/api/v1/recommendations",
            data=json.dumps({
                "name": "Fabio API identity",
                "summary": "API-created recommendations should point at Fabio.",
                "payload": {},
            }),
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": self.api_key,
            },
        )

        self.assertEqual(resp.status_code, 200, resp.text)
        rec = self.env["southbrook.hermes.recommendation"].browse(
            resp.json()["recommendation_id"],
        )
        self.assertEqual(rec.agent_partner_id, partner)
