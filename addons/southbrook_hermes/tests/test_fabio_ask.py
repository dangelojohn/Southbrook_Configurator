# SPDX-License-Identifier: LGPL-3.0-only
import unittest

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes", "fabio_ask")
class TestFabioAsk(TransactionCase):

    def test_internal_answer_lists_production_blockers(self):
        if "southbrook.mi.check" not in self.env:
            raise unittest.SkipTest(
                "southbrook_manufacturing_intelligence not installed"
            )
        self.env["southbrook.mi.check"].create({
            "name": "Missing cutlist",
            "severity": "blocker",
            "category": "production",
            "message": "Manufacturing intelligence requires a linked cutlist.",
            "recommendation": "Create or link a production package with a cutlist.",
        })

        question = self.env["southbrook.hermes.question"].create({
            "question": "What production blockers need attention?",
            "scope": "internal",
        })
        question.action_answer()

        self.assertEqual(question.state, "answered")
        self.assertIn("Missing cutlist", question.answer)
        self.assertIn("Create or link a production package", question.answer)

    def test_internal_answer_describes_base_production_users(self):
        question = self.env["southbrook.hermes.question"].create({
            "question": "What does each base production user do?",
            "scope": "internal",
        })
        question.action_answer()

        self.assertIn("Alex Estimator", question.answer)
        self.assertIn("Chris CNC", question.answer)
        self.assertIn("Morgan Production", question.answer)

    def test_customer_answer_is_scoped_to_partner_projects(self):
        partner = self.env["res.partner"].create({"name": "Portal Customer"})
        other_partner = self.env["res.partner"].create({"name": "Other Customer"})
        own_project = self.env["sb.kitchen.project"].create({
            "name": "Own Kitchen",
            "partner_id": partner.id,
            "state": "awaiting_customer",
        })
        other_project = self.env["sb.kitchen.project"].create({
            "name": "Other Kitchen",
            "partner_id": other_partner.id,
            "state": "in_production",
        })

        question = self.env["southbrook.hermes.question"].create({
            "question": "What is the status of my kitchen?",
            "scope": "customer",
            "partner_id": partner.id,
            "project_id": own_project.id,
        })
        question.action_answer()

        self.assertIn("Own Kitchen", question.answer)
        self.assertIn("Awaiting Customer", question.answer)
        self.assertNotIn(other_project.name, question.answer)

    def test_answer_can_be_converted_to_draft_recommendation(self):
        question = self.env["southbrook.hermes.question"].create({
            "question": "Create a follow up for the production manager.",
            "scope": "internal",
        })
        question.action_answer()
        question.action_create_recommendation()

        self.assertTrue(question.recommendation_id)
        self.assertEqual(question.recommendation_id.state, "draft")
        self.assertEqual(question.recommendation_id.recommendation_type, "followup")

    def test_backend_ask_menu_is_available(self):
        menu = self.env.ref("southbrook_hermes.menu_hermes_questions")
        action = self.env.ref("southbrook_hermes.action_hermes_question")
        form = self.env.ref("southbrook_hermes.view_hermes_question_form")

        self.assertEqual(menu.name, "Ask")
        self.assertEqual(action.name, "Ask Fabio")
        self.assertIn("Ask Fabio", form.arch_db)
