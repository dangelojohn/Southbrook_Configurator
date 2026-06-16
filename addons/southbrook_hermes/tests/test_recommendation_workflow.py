# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hermes")
class TestHermesRecommendationWorkflow(TransactionCase):

    def setUp(self):
        super().setUp()
        self.project = self.env["project.project"].create({
            "name": "HERMES Test Project",
        })

    def _task_recommendation(self, **extra):
        vals = {
            "name": "Follow up on commercial estimate",
            "recommendation_type": "task",
            "summary": "Review the latest customer requirements.",
            "proposed_action": "Create a task for a human estimator.",
            "payload_json": json.dumps({
                "project_id": self.project.id,
                "task_name": "Review commercial estimate",
                "description": "Check the latest plans and pricing notes.",
            }),
            "agent_run_id": "test-run-001",
            "model_provider": "openai",
            "model_name": "gpt-5",
        }
        vals.update(extra)
        return self.env["southbrook.hermes.recommendation"].create(vals)

    def test_recommendation_starts_as_draft(self):
        rec = self._task_recommendation()

        self.assertEqual(rec.state, "draft")
        self.assertFalse(rec.reviewer_id)
        self.assertFalse(rec.created_task_id)

    def test_payload_json_must_be_object(self):
        with self.assertRaises(ValidationError):
            self._task_recommendation(payload_json="[1, 2, 3]")

    def test_apply_requires_approval(self):
        rec = self._task_recommendation()

        with self.assertRaises(UserError):
            rec.action_apply()

    def test_approved_task_recommendation_creates_project_task(self):
        rec = self._task_recommendation()

        rec.action_mark_ready()
        rec.action_approve()
        rec.action_apply()

        self.assertEqual(rec.state, "applied")
        self.assertTrue(rec.created_task_id)
        self.assertEqual(rec.created_task_id.project_id, self.project)
        self.assertEqual(rec.created_task_id.name, "Review commercial estimate")
        self.assertEqual(rec.reviewer_id, self.env.user)
        self.assertTrue(rec.reviewed_date)
        self.assertTrue(rec.applied_date)
