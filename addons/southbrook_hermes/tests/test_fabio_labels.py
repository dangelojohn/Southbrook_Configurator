# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes", "fabio_labels")
class TestFabioLabels(TransactionCase):

    def test_odoo_visible_labels_use_fabio(self):
        menu = self.env.ref("southbrook_hermes.menu_hermes_root")
        action = self.env.ref("southbrook_hermes.action_hermes_recommendation")
        group = self.env.ref("southbrook_hermes.group_hermes_reviewer")
        form = self.env.ref("southbrook_hermes.view_hermes_recommendation_form")

        self.assertEqual(menu.name, "Fabio")
        self.assertEqual(action.name, "Fabio Recommendations")
        self.assertEqual(group.name, "Fabio Reviewer")
        self.assertIn("Apply this Fabio recommendation?", form.arch_db)

    def test_odoo_administrators_can_see_fabio_menu_by_default(self):
        reviewer_group = self.env.ref("southbrook_hermes.group_hermes_reviewer")
        settings_group = self.env.ref("base.group_system")
        admin = self.env.ref("base.user_admin")

        self.assertIn(reviewer_group, settings_group.implied_ids)
        self.assertTrue(
            admin.has_group("southbrook_hermes.group_hermes_reviewer"),
        )

    def test_technical_identifiers_stay_hermes(self):
        self.assertIn("southbrook.hermes.recommendation", self.env)
        self.assertTrue(
            self.env["ir.model"].sudo().search([
                ("model", "=", "southbrook.hermes.recommendation"),
            ], limit=1),
        )
