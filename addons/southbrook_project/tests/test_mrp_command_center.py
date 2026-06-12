# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "mrp_command")
class TestMrpCommandCenter(TransactionCase):

    def _new_task(self, **vals):
        project = self.env["project.project"].create({
            "name": vals.pop("project_name", "MRP Command Test Project"),
        })
        defaults = {
            "name": "SO24091 Kitchen A",
            "project_id": project.id,
        }
        defaults.update(vals)
        return self.env["project.task"].create(defaults)

    def test_ready_task_scores_100(self):
        task = self._new_task()
        gates = {
            "estimate": {
                "state": "ready",
                "message": "Estimate approved",
                "action": False,
                "blocking": False,
            },
            "engineering": {
                "state": "ready",
                "message": "Drawings approved",
                "action": False,
                "blocking": False,
            },
            "bom_cutlist": {
                "state": "ready",
                "message": "BOM and cutlist ready",
                "action": False,
                "blocking": False,
            },
            "purchasing": {
                "state": "ready",
                "message": "Purchasing ready",
                "action": False,
                "blocking": False,
            },
            "materials": {
                "state": "ready",
                "message": "Materials ready",
                "action": False,
                "blocking": False,
            },
            "tooling": {
                "state": "ready",
                "message": "Tooling ready",
                "action": False,
                "blocking": False,
            },
            "labor": {
                "state": "ready",
                "message": "Labor assigned",
                "action": False,
                "blocking": False,
            },
            "equipment": {
                "state": "ready",
                "message": "Equipment ready",
                "action": False,
                "blocking": False,
            },
            "schedule": {
                "state": "ready",
                "message": "Schedule ready",
                "action": False,
                "blocking": False,
            },
            "delivery": {
                "state": "ready",
                "message": "Delivery not due",
                "action": False,
                "blocking": False,
            },
            "install": {
                "state": "ready",
                "message": "Install not due",
                "action": False,
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertEqual(score, 100)
        self.assertEqual(state, "ready")
        self.assertFalse(blocked_gate)
        self.assertEqual(summary, "All release gates are ready.")
        self.assertFalse(next_action)

    def test_blocked_gate_caps_score_and_summary(self):
        task = self._new_task()
        gates = {
            "bom_cutlist": {
                "state": "blocked",
                "message": "BOM or cutlist missing",
                "action": "Generate the cutlist before release.",
                "blocking": True,
            },
            "tooling": {
                "state": "warning",
                "message": "Tooling has warnings",
                "action": "Review optional tooling.",
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 69)
        self.assertEqual(state, "blocked")
        self.assertEqual(blocked_gate, "bom_cutlist")
        self.assertIn("BOM or cutlist missing", summary)
        self.assertEqual(next_action, "Generate the cutlist before release.")

    def test_warning_gate_sets_at_risk_state(self):
        task = self._new_task()
        gates = {
            "tooling": {
                "state": "warning",
                "message": "Tooling has warnings",
                "action": "Review optional tooling.",
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 89)
        self.assertEqual(state, "at_risk")
        self.assertFalse(blocked_gate)
        self.assertIn("Tooling has warnings", summary)
        self.assertEqual(next_action, "Review optional tooling.")

    def test_not_started_gate_sets_at_risk_state(self):
        task = self._new_task()
        gates = {
            "engineering": {
                "state": "not_started",
                "message": "Engineering not started",
                "action": "Start engineering.",
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 89)
        self.assertEqual(state, "at_risk")
        self.assertFalse(blocked_gate)
        self.assertIn("Engineering not started", summary)
        self.assertEqual(next_action, "Start engineering.")

    def test_unknown_gate_state_sets_at_risk_state(self):
        task = self._new_task()
        gates = {
            "schedule": {
                "state": "deferred",
                "message": "Schedule status imported from legacy data",
                "action": False,
                "blocking": False,
            },
        }
        score, state, blocked_gate, summary, next_action = (
            task._southbrook_score_from_gates(gates)
        )
        self.assertLessEqual(score, 89)
        self.assertEqual(state, "at_risk")
        self.assertFalse(blocked_gate)
        self.assertIn("Unknown gate state 'deferred'", summary)
        self.assertIn("Unknown gate state 'deferred'", next_action)

    def test_computed_fields_include_gate_json(self):
        task = self._new_task()
        self.assertEqual(task.x_southbrook_readiness_score, 100)
        self.assertEqual(task.x_southbrook_readiness_state, "ready")
        self.assertFalse(task.x_southbrook_blocking_gate)
        self.assertEqual(
            task.x_southbrook_blocker_summary,
            "All release gates are ready.",
        )
        self.assertFalse(task.x_southbrook_next_action)

        rows = json.loads(task.x_southbrook_gate_json)
        self.assertEqual(len(rows), 11)
        self.assertEqual(rows[0]["gate"], "estimate")
        self.assertEqual(rows[0]["label"], "Estimate")
        for row in rows:
            self.assertEqual(
                set(row),
                {"gate", "label", "state", "message", "action", "blocking"},
            )
            self.assertEqual(row["state"], "ready")
            self.assertFalse(row["action"])
            self.assertFalse(row["blocking"])
