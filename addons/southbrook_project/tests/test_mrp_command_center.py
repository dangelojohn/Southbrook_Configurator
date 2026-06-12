# SPDX-License-Identifier: LGPL-3.0-only
from odoo.exceptions import UserError
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
