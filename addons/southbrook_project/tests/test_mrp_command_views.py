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
