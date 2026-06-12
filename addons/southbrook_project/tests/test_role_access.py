# SPDX-License-Identifier: LGPL-3.0-only
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install", "southbrook", "mrp_command")
class TestSouthbrookProjectRoleAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pm_user = new_test_user(
            cls.env,
            login="southbrook_pm",
            groups="southbrook_project.group_southbrook_pm",
        )
        cls.shop_lead_user = new_test_user(
            cls.env,
            login="southbrook_shop_lead",
            groups="southbrook_project.group_southbrook_shop_lead",
        )
        cls.designer_user = new_test_user(
            cls.env,
            login="southbrook_designer",
            groups="southbrook_project.group_southbrook_designer",
        )
        cls.installer_user = new_test_user(
            cls.env,
            login="southbrook_installer",
            groups="southbrook_project.group_southbrook_installer",
        )
        cls.executive_user = new_test_user(
            cls.env,
            login="southbrook_executive",
            groups="southbrook_project.group_southbrook_executive",
        )
        cls.internal_user = new_test_user(
            cls.env,
            login="southbrook_internal",
            groups="base.group_user,project.group_project_user",
        )

    def test_pm_can_manage_job_templates_and_data_quality(self):
        template = self.env["southbrook.job.template"].with_user(
            self.pm_user
        ).create({
            "name": "PM Managed Kitchen",
            "job_type": "kitchen",
            "cabinet_family": "base",
        })
        issue = self.env["southbrook.project.data.quality.issue"].with_user(
            self.pm_user
        ).create({
            "name": "PM data quality issue",
            "issue_type": "blank_install_due",
            "model_name": "project.task",
            "res_id": 1,
            "recommended_action": "Set install due.",
        })

        template.with_user(self.pm_user).write({"unit_count": 2})
        issue.with_user(self.pm_user).action_exclude_from_pm_reporting()
        self.assertEqual(issue.state, "excluded")

    def test_southbrook_roles_include_project_access(self):
        self.assertTrue(self.pm_user.has_group("project.group_project_manager"))
        for user in (
            self.shop_lead_user,
            self.designer_user,
            self.installer_user,
            self.executive_user,
        ):
            self.assertTrue(user.has_group("project.group_project_user"))

    def test_pm_can_start_job_from_template(self):
        project = self.env["project.project"].create({
            "name": "PM Template Start Project",
        })
        template = self.env["southbrook.job.template"].create({
            "name": "PM Started Kitchen",
            "job_type": "kitchen",
            "cabinet_family": "base",
            "checklist_template_ids": [
                (0, 0, {
                    "name": "CAD approved",
                    "gate": "engineering",
                    "required": True,
                }),
            ],
        })

        action = template.with_user(self.pm_user).action_create_project_job(project.id)
        task = self.env["project.task"].browse(action["res_id"])

        self.assertEqual(task.project_id, project)
        self.assertEqual(task.x_southbrook_job_type, "kitchen")
        self.assertEqual(len(task.x_southbrook_checklist_item_ids), 1)

    def test_shop_lead_can_update_checklist_but_not_create_templates(self):
        project = self.env["project.project"].create({"name": "Role Access Project"})
        task = self.env["project.task"].create({
            "name": "Shop Lead Job",
            "project_id": project.id,
        })
        item = self.env["southbrook.job.checklist.item"].create({
            "task_id": task.id,
            "name": "Cutlist confirmed",
            "gate": "bom_cutlist",
        })

        item.with_user(self.shop_lead_user).write({"done": True})
        self.assertTrue(item.done)
        with self.assertRaises(AccessError):
            self.env["southbrook.job.template"].with_user(
                self.shop_lead_user
            ).create({
                "name": "Unauthorized Template",
                "job_type": "kitchen",
            })

    def test_designer_installer_and_executive_have_readonly_checklist_access(self):
        project = self.env["project.project"].create({"name": "Read Only Project"})
        task = self.env["project.task"].create({
            "name": "Read Only Job",
            "project_id": project.id,
        })
        item = self.env["southbrook.job.checklist.item"].create({
            "task_id": task.id,
            "name": "CAD released",
            "gate": "engineering",
        })
        for user in (
            self.designer_user,
            self.installer_user,
            self.executive_user,
        ):
            self.assertEqual(item.with_user(user).read(["name"])[0]["name"], "CAD released")
            with self.assertRaises(AccessError):
                item.with_user(user).write({"done": True})

    def test_executive_can_read_but_not_change_data_quality_issues(self):
        issue = self.env["southbrook.project.data.quality.issue"].create({
            "name": "Executive read issue",
            "issue_type": "queue_overlap",
            "model_name": "project.task",
            "res_id": 1,
            "recommended_action": "Pick one PM owner.",
        })

        self.assertEqual(issue.with_user(self.executive_user).read([
            "recommended_action",
        ])[0]["recommended_action"], "Pick one PM owner.")
        with self.assertRaises(AccessError):
            issue.with_user(self.executive_user).action_archive_issue()

    def test_internal_user_can_read_task_state_without_checklist_detail(self):
        project = self.env["project.project"].create({"name": "Internal Read Project"})
        task = self.env["project.task"].create({
            "name": "Internal Read Job",
            "project_id": project.id,
        })
        self.env["southbrook.job.checklist.item"].create({
            "task_id": task.id,
            "name": "Checklist hidden from generic users",
            "gate": "engineering",
        })

        values = task.with_user(self.internal_user).read([
            "x_southbrook_checklist_state",
        ])[0]

        self.assertEqual(values["x_southbrook_checklist_state"], "blocked")
        self.assertNotIn("Checklist hidden", task.x_southbrook_blocker_summary)
        with self.assertRaises(AccessError):
            task.with_user(self.internal_user).read([
                "x_southbrook_checklist_summary",
            ])
