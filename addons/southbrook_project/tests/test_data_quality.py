# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "mrp_command")
class TestSouthbrookProjectDataQuality(TransactionCase):

    def test_dry_run_report_identifies_project_data_issues(self):
        project = self.env["project.project"].create({
            "name": "Data Quality Project",
        })
        task = self.env["project.task"].create({
            "name": "Kitchen Missing Install Due",
            "project_id": project.id,
            "x_southbrook_job_type": "kitchen",
        })
        product = self.env["product.product"].create({
            "name": "SB Placeholder Product",
            "default_code": "SB-PLACEHOLDER",
            "standard_price": 0.0,
        })

        issues = self.env[
            "southbrook.project.data.quality.issue"
        ].action_generate_dry_run_report()

        self.assertIn(task.id, issues.filtered(
            lambda issue: issue.issue_type == "blank_install_due"
        ).mapped("res_id"))
        self.assertIn(product.id, issues.filtered(
            lambda issue: issue.issue_type == "placeholder_cost"
            and issue.model_name == "product.product"
        ).mapped("res_id"))
        self.assertTrue(all(issue.dry_run for issue in issues))

    def test_cleanup_actions_do_not_delete_source_records(self):
        project = self.env["project.project"].create({
            "name": "Cleanup Safety Project",
        })
        task = self.env["project.task"].create({
            "name": "Kitchen Missing Install Due",
            "project_id": project.id,
            "x_southbrook_job_type": "kitchen",
        })
        issue = self.env["southbrook.project.data.quality.issue"].create({
            "name": "Missing install due",
            "issue_type": "blank_install_due",
            "model_name": "project.task",
            "res_id": task.id,
            "recommended_action": "Set an install due date.",
        })

        issue.action_exclude_from_pm_reporting()
        self.assertTrue(task.exists())
        self.assertEqual(issue.state, "excluded")

        issue.action_archive_issue()
        self.assertTrue(task.exists())
        self.assertEqual(issue.state, "archived")
        self.assertFalse(issue.active)

    def test_dry_run_rerun_preserves_excluded_issue_state(self):
        project = self.env["project.project"].create({
            "name": "Cleanup Persistence Project",
        })
        task = self.env["project.task"].create({
            "name": "Kitchen Missing Install Due",
            "project_id": project.id,
            "x_southbrook_job_type": "kitchen",
        })
        Issue = self.env["southbrook.project.data.quality.issue"]

        first = Issue.action_generate_dry_run_report().filtered(
            lambda issue: issue.issue_type == "blank_install_due"
            and issue.model_name == "project.task"
            and issue.res_id == task.id
        )
        first.action_exclude_from_pm_reporting()
        second = Issue.action_generate_dry_run_report().filtered(
            lambda issue: issue.issue_type == "blank_install_due"
            and issue.model_name == "project.task"
            and issue.res_id == task.id
        )

        self.assertEqual(second, first)
        self.assertEqual(second.state, "excluded")
