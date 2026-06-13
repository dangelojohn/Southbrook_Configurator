# SPDX-License-Identifier: LGPL-3.0-only
from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "mrp_command")
class TestMrpCommandViews(TransactionCase):

    def test_project_task_form_has_mrp_command_panel(self):
        view = self.env.ref("southbrook_project.view_project_task_form_inherit_southbrook")
        arch = view.arch_db
        for marker in [
            "southbrook_mrp_command",
            "southbrook_release_checklist",
            "southbrook_project.group_southbrook_pm",
            "x_southbrook_readiness_score",
            "x_southbrook_readiness_state",
            "x_southbrook_blocking_gate",
            "x_southbrook_blocker_summary",
            "action_southbrook_release_to_production",
            "action_southbrook_recompute_mrp_readiness",
        ]:
            self.assertIn(marker, arch)

    def test_legacy_readiness_line_count_field_exists_for_deployed_views(self):
        self.assertIn("readiness_line_count", self.env["project.task"]._fields)

    def test_mrp_command_center_actions_load(self):
        xmlids = [
            "southbrook_project.view_project_task_list_mrp_command",
            "southbrook_project.view_project_task_search_mrp_command",
            "southbrook_project.view_project_task_kanban_mrp_command",
            "southbrook_project.action_mrp_command_daily_meeting",
            "southbrook_project.action_mrp_command_daily_meeting_kanban_view",
            "southbrook_project.action_mrp_command_daily_meeting_list_view",
            "southbrook_project.action_mrp_command_blocked_jobs",
            "southbrook_project.action_mrp_command_ready_jobs",
            "southbrook_project.action_mrp_command_at_risk_jobs",
            "southbrook_project.menu_mrp_command_daily_meeting",
            "southbrook_project.menu_mrp_command_blocked_jobs",
            "southbrook_project.menu_mrp_command_ready_jobs",
            "southbrook_project.menu_mrp_command_at_risk_jobs",
            "southbrook_project.view_southbrook_job_template_list",
            "southbrook_project.view_southbrook_job_template_form",
            "southbrook_project.action_southbrook_job_templates",
            "southbrook_project.menu_southbrook_job_templates",
            "southbrook_project.view_southbrook_data_quality_issue_list",
            "southbrook_project.view_southbrook_data_quality_issue_form",
            "southbrook_project.action_southbrook_data_quality_issues",
            "southbrook_project.server_action_southbrook_data_quality_dry_run",
            "southbrook_project.menu_southbrook_generate_data_quality_issues",
            "southbrook_project.menu_southbrook_data_quality_issues",
            "southbrook_project.group_southbrook_pm",
            "southbrook_project.group_southbrook_shop_lead",
            "southbrook_project.group_southbrook_designer",
            "southbrook_project.group_southbrook_installer",
            "southbrook_project.group_southbrook_executive",
        ]
        for xmlid in xmlids:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False), xmlid)
        action = self.env.ref("southbrook_project.action_mrp_command_daily_meeting")
        self.assertIn(
            self.env.ref("southbrook_project.view_project_task_kanban_mrp_command"),
            action.view_ids.mapped("view_id"),
        )
        self.assertIn(
            self.env.ref("southbrook_project.view_project_task_list_mrp_command"),
            action.view_ids.mapped("view_id"),
        )
        search = self.env.ref("southbrook_project.view_project_task_search_mrp_command")
        for marker in [
            "readiness_blocked",
            "readiness_ready",
            "readiness_at_risk",
            "group_blocking_gate",
            "group_readiness_state",
            "group_cabinet_family",
        ]:
            self.assertIn(marker, search.arch_db)
        for menu_xmlid in [
            "southbrook_project.menu_mrp_command_daily_meeting",
            "southbrook_project.menu_mrp_command_blocked_jobs",
            "southbrook_project.menu_mrp_command_ready_jobs",
            "southbrook_project.menu_mrp_command_at_risk_jobs",
        ]:
            groups = self.env.ref(menu_xmlid).groups_id.get_external_id().values()
            self.assertIn("southbrook_project.group_southbrook_pm", groups)

    def test_mrp_command_readiness_fields_are_readonly_in_views(self):
        readonly_fields = [
            "x_southbrook_readiness_score",
            "x_southbrook_readiness_state",
            "x_southbrook_blocking_gate",
            "x_southbrook_next_action",
        ]
        views = [
            self.env.ref("southbrook_project.view_project_task_form_inherit_southbrook"),
            self.env.ref("southbrook_project.view_project_task_list_mrp_command"),
            self.env.ref("southbrook_project.view_project_task_kanban_mrp_command"),
        ]
        for view in views:
            arch = etree.fromstring(view.arch_db.encode())
            for field_name in readonly_fields:
                nodes = arch.xpath(".//field[@name='%s']" % field_name)
                self.assertTrue(nodes, "%s missing from %s" % (field_name, view.name))
                self.assertTrue(
                    all(node.get("readonly") == "1" for node in nodes),
                    "%s editable in %s" % (field_name, view.name),
                )

    def test_mrp_command_kanban_template_uses_record_values(self):
        view = self.env.ref("southbrook_project.view_project_task_kanban_mrp_command")
        arch = etree.fromstring(view.arch_db.encode())

        self.assertFalse(
            arch.xpath(".//templates//field"),
            "Kanban card template should avoid field widgets; they can break "
            "when archInfo.fieldNodes is stale or incomplete.",
        )
        self.assertTrue(arch.xpath(".//templates//t[contains(@t-esc, 'record.')]"))
