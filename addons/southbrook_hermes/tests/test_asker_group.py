# SPDX-License-Identifier: LGPL-3.0-only
"""Regression test for the 2026-07-02 Fabio Asker group.

Before: only admin (base.group_system → group_hermes_reviewer) had
create/read/write on southbrook.hermes.question. Non-admin users
hitting /odoo/action-<id>/new got AccessError on Save. The web client
rendered this as "I can't make a new record."

After: every internal user is implied into group_hermes_asker via
base.group_user, granting perm on Question (scoped by ir.rule to own
rows). Recommendation stays reviewer-only.
"""
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes", "fabio_asker")
class TestFabioAskerGroup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_user = cls.env["res.users"].create({
            "name": "Fabio Asker Test User",
            "login": "fabio_asker_test",
            "email": "fabio_asker_test@example.com",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def test_internal_user_gets_asker_group_via_implication(self):
        self.assertTrue(
            self.internal_user.has_group(
                "southbrook_hermes.group_hermes_asker"
            ),
            "base.group_user should imply group_hermes_asker so every "
            "internal user can ask Fabio.",
        )

    def test_internal_user_is_not_a_reviewer(self):
        self.assertFalse(
            self.internal_user.has_group(
                "southbrook_hermes.group_hermes_reviewer"
            ),
            "A plain internal user should NOT be a Fabio Reviewer.",
        )

    def test_asker_can_create_question(self):
        question = self.env["southbrook.hermes.question"].with_user(
            self.internal_user
        ).create({
            "question": "What production blockers need attention?",
            "scope": "internal",
        })
        self.assertTrue(question.id)
        self.assertEqual(question.asked_by_id, self.internal_user)

    def test_asker_action_answer_writes_answer(self):
        question = self.env["southbrook.hermes.question"].with_user(
            self.internal_user
        ).create({
            "question": "What can Fabio help with?",
            "scope": "internal",
        })
        question.action_answer()
        self.assertEqual(question.state, "answered")
        self.assertTrue(question.answer)

    def test_asker_cannot_create_recommendation(self):
        with self.assertRaises(AccessError):
            self.env["southbrook.hermes.recommendation"].with_user(
                self.internal_user
            ).create({
                "name": "Unauthorized rec",
                "recommendation_type": "followup",
                "priority": "normal",
                "summary": "Nope.",
                "proposed_action": "Nope.",
                "payload_json": "{}",
                "source_model": "res.partner",
                "source_res_id": 1,
                "agent_run_id": "test",
                "model_provider": "test",
                "model_name": "test",
            })

    def test_asker_only_sees_own_questions(self):
        other_user = self.env["res.users"].create({
            "name": "Second Asker",
            "login": "fabio_asker_test2",
            "email": "fabio_asker_test2@example.com",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })

        q_mine = self.env["southbrook.hermes.question"].with_user(
            self.internal_user
        ).create({
            "question": "Mine — should be visible to me.",
            "scope": "internal",
        })
        q_theirs = self.env["southbrook.hermes.question"].with_user(
            other_user
        ).create({
            "question": "Theirs — should be invisible to me.",
            "scope": "internal",
        })

        visible = self.env["southbrook.hermes.question"].with_user(
            self.internal_user
        ).search([])
        self.assertIn(q_mine, visible)
        self.assertNotIn(q_theirs, visible)

    def test_reviewer_sees_all_questions(self):
        q_asker = self.env["southbrook.hermes.question"].with_user(
            self.internal_user
        ).create({
            "question": "Asker's question.",
            "scope": "internal",
        })
        admin = self.env.ref("base.user_admin")
        visible = self.env["southbrook.hermes.question"].with_user(
            admin
        ).search([])
        self.assertIn(q_asker, visible)
