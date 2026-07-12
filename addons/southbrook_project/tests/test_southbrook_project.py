# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for southbrook_project — the module previously shipped with zero
coverage. Covers the three logic-bearing pieces: the top-level task count
(subtask/closed exclusion), the display_name SO suffix, and the post_init
backfill (fill-blanks idempotency)."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_project")
class TestSouthbrookProject(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Project = cls.env["project.project"]
        cls.Task = cls.env["project.task"]

    # ─── Top-level task count ───────────────────────────────────────
    def test_top_level_count_excludes_subtasks_and_closed(self):
        project = self.Project.create({"name": "Shop Floor"})
        t1 = self.Task.create({"name": "Job 1", "project_id": project.id})
        self.Task.create({"name": "Job 2", "project_id": project.id})
        # Closed top-level task — excluded by state.
        done = self.Task.create({"name": "Job 3", "project_id": project.id})
        done.write({"state": "1_done"})
        # Subtask under Job 1 — excluded by parent_id.
        self.Task.create({
            "name": "Sub-step", "project_id": project.id,
            "parent_id": t1.id,
        })
        self.assertEqual(
            project.southbrook_top_level_task_count, 2,
            "only open top-level tasks count (not subtasks, not closed)")

    def test_top_level_count_recomputes_on_state_change(self):
        project = self.Project.create({"name": "Recompute"})
        t = self.Task.create({"name": "Job", "project_id": project.id})
        self.assertEqual(project.southbrook_top_level_task_count, 1)
        t.write({"state": "1_done"})
        self.assertEqual(
            project.southbrook_top_level_task_count, 0,
            "@api.depends must refresh the count when a task closes")

    # ─── display_name SO suffix ─────────────────────────────────────
    def test_display_name_suffixes_sale_order(self):
        partner = self.env["res.partner"].create({"name": "Acme Kitchens"})
        so = self.env["sale.order"].create({"partner_id": partner.id})
        project = self.Project.create({"name": "P"})
        task = self.Task.create({
            "name": "Cabinet Job", "project_id": project.id,
            "x_southbrook_sale_order_id": so.id,
        })
        self.assertTrue(task.display_name.startswith("Cabinet Job"))
        self.assertIn("[%s]" % so.name, task.display_name)

    def test_display_name_no_suffix_without_sale_order(self):
        project = self.Project.create({"name": "P"})
        task = self.Task.create({"name": "Plain Job", "project_id": project.id})
        self.assertNotIn("[", task.display_name)

    # ─── priority default ───────────────────────────────────────────
    def test_priority_defaults_to_standard(self):
        project = self.Project.create({"name": "P"})
        task = self.Task.create({"name": "Job", "project_id": project.id})
        self.assertEqual(task.x_southbrook_priority, "standard")

    # ─── backfill ───────────────────────────────────────────────────
    def test_backfill_fills_blanks_then_is_idempotent(self):
        project = self.Project.create({"name": "Backfill Target"})
        filled = project._southbrook_backfill_defaults()
        self.assertIn("description", filled)
        self.assertIn("date_start", filled)
        self.assertIn("allow_task_dependencies", filled)
        self.assertIn("allow_milestones", filled)
        self.assertTrue(project.description)
        self.assertTrue(project.date_start)
        self.assertTrue(project.allow_task_dependencies)
        self.assertTrue(project.allow_milestones)
        # Second run must write nothing (all fields now populated/True).
        self.assertEqual(project._southbrook_backfill_defaults(), [])

    def test_backfill_does_not_stomp_operator_description(self):
        project = self.Project.create({
            "name": "Has Description",
            "description": "<p>operator wrote this</p>",
        })
        filled = project._southbrook_backfill_defaults()
        self.assertNotIn("description", filled,
                         "a non-blank description must be left untouched")
        self.assertEqual(project.description, "<p>operator wrote this</p>")
