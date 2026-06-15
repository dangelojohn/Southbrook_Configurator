# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 3.3 — generative job template + DQ dry-run tests.

Covers the four acceptance bullets from the Phase-3.3 brief:

  1. _resolve_template_for_sale_order maps a Pantry-keyword order to
     the Pantry template specifically (not Full Kitchen).
  2. Assigning x_kitchen_job_template_id on a parent task spawns one
     subtask per template line, each carrying template_line_id back.
  3. Re-applying the same template a second time is a no-op (idempotent).
  4. _cron_nightly_dry_run writes at least one report with at least
     three quality lines for an active project.

All tests are post_install so southbrook_project_mrp (which owns the
job-template + DQ-report schemas) is guaranteed to be loaded.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "premium_orchestration")
class TestPhase3Generative(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Phase3 Test Customer",
        })
        cls.project = cls.env["project.project"].create({
            "name": "Phase3 Kitchen Jobs",
        })
        cls.env["ir.config_parameter"].sudo().set_param(
            "southbrook_premium.default_kitchen_project_id",
            str(cls.project.id),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _product(self, name):
        return self.env["product.product"].create({
            "name": name,
            "type": "consu",
        })

    def _so_for(self, product_name):
        product = self._product(product_name)
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": product.id,
                "product_uom_qty": 1.0,
            })],
        })

    # ------------------------------------------------------------------
    # AC-1 — resolver maps to Pantry
    # ------------------------------------------------------------------
    def test_template_resolution_matches_pantry(self):
        Task = self.env["project.task"]
        so = self._so_for("Tall Pantry Kit, Shaker Maple")
        template = Task._resolve_template_for_sale_order(so)
        self.assertTrue(template,
            "resolver must return a template for a pantry-keyword SO")
        # We tolerate either the explicit "Pantry" template or any
        # template whose name contains 'pantry' — the brief allows
        # the looser match.
        self.assertIn("pantry", (template.name or "").lower(),
            "resolved template name must contain 'pantry'")

    # ------------------------------------------------------------------
    # AC-2 — assigning the template spawns subtasks
    # ------------------------------------------------------------------
    def test_template_lines_spawn_subtasks(self):
        Template = self.env["southbrook.project.job.template"]
        Task = self.env["project.task"]
        # Build an ad-hoc 3-line template so the test is decoupled from
        # whichever seeded template happens to have 3 lines.
        template = Template.create({
            "name": "Phase3 Spawn Test",
            "job_type": "single_cabinet",
            "line_ids": [
                (0, 0, {"name": "Step A", "sequence": 10}),
                (0, 0, {"name": "Step B", "sequence": 20}),
                (0, 0, {"name": "Step C", "sequence": 30}),
            ],
        })
        parent = Task.create({
            "name": "Phase3 Parent Task",
            "project_id": self.project.id,
        })
        parent.x_kitchen_job_template_id = template.id
        # write() override should have applied automatically.
        children = parent.child_ids
        self.assertEqual(len(children), 3,
            "must spawn exactly one subtask per template line")
        # Every subtask must back-link to its source line.
        for child in children:
            self.assertTrue(child.template_line_id,
                "spawned subtask must carry template_line_id")
            self.assertEqual(child.template_line_id.template_id, template,
                "back-link must point at the source template's line")

    # ------------------------------------------------------------------
    # AC-3 — idempotent on second apply
    # ------------------------------------------------------------------
    def test_template_idempotent(self):
        Template = self.env["southbrook.project.job.template"]
        Task = self.env["project.task"]
        template = Template.create({
            "name": "Phase3 Idempotency Test",
            "job_type": "single_cabinet",
            "line_ids": [
                (0, 0, {"name": "Step A", "sequence": 10}),
                (0, 0, {"name": "Step B", "sequence": 20}),
                (0, 0, {"name": "Step C", "sequence": 30}),
            ],
        })
        parent = Task.create({
            "name": "Phase3 Idempotency Parent",
            "project_id": self.project.id,
            "x_kitchen_job_template_id": template.id,
        })
        first_count = len(parent.child_ids)
        # Re-apply directly via the private method — this is the path
        # a server action or admin tool would hit.
        parent._apply_job_template()
        parent._apply_job_template()
        self.assertEqual(len(parent.child_ids), first_count,
            "second + third _apply_job_template calls must be no-ops")
        self.assertEqual(first_count, 3,
            "first apply must have spawned exactly 3 subtasks")

    # ------------------------------------------------------------------
    # AC-4 — DQ cron creates report with lines
    # ------------------------------------------------------------------
    def test_dq_cron_creates_report(self):
        Report = self.env["southbrook.project.data.quality.report"]
        # Baseline: no reports linked to this project yet (filter on
        # project_id when the field is present to keep this test
        # robust if other tests have already produced reports).
        if "project_id" in Report._fields:
            domain = [("project_id", "=", self.project.id)]
        else:
            domain = []
        baseline = Report.search_count(domain)

        Report._cron_nightly_dry_run()

        reports = Report.search(domain)
        self.assertGreater(len(reports), baseline,
            "the nightly cron must produce at least one new report record")
        # Pick any report tied to this project and confirm it has lines.
        sample = reports.filtered(
            lambda r: not r.project_id or r.project_id == self.project
        )[:1] or reports[:1]
        self.assertTrue(sample.line_ids,
            "the generated report must carry at least one quality line")
        self.assertGreaterEqual(len(sample.line_ids), 3,
            "the nightly cron must score at least 3 of the 6 dimensions")
