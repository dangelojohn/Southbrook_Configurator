# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "mrp_command")
class TestMrpCommandViews(TransactionCase):

    def test_project_task_form_has_mrp_command_panel(self):
        view = self.env.ref("southbrook_project.view_project_task_form_inherit_southbrook")
        arch = view.arch_db
        for marker in [
            "southbrook_mrp_command",
            "x_southbrook_readiness_score",
            "x_southbrook_readiness_state",
            "x_southbrook_blocking_gate",
            "x_southbrook_blocker_summary",
            "action_southbrook_release_to_production",
            "action_southbrook_recompute_mrp_readiness",
        ]:
            self.assertIn(marker, arch)

    def test_mrp_command_center_actions_load(self):
        xmlids = [
            "southbrook_project.view_project_task_list_mrp_command",
            "southbrook_project.view_project_task_search_mrp_command",
            "southbrook_project.view_project_task_kanban_mrp_command",
            "southbrook_project.action_mrp_command_daily_meeting",
            "southbrook_project.action_mrp_command_blocked_jobs",
            "southbrook_project.action_mrp_command_ready_jobs",
            "southbrook_project.action_mrp_command_at_risk_jobs",
        ]
        for xmlid in xmlids:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False), xmlid)
        search = self.env.ref("southbrook_project.view_project_task_search_mrp_command")
        for marker in [
            "readiness_blocked",
            "readiness_ready",
            "readiness_at_risk",
            "group_blocking_gate",
            "group_readiness_state",
        ]:
            self.assertIn(marker, search.arch_db)
