# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 1.1 — Spine Activation tests.

Covers the five acceptance criteria from the Phase-1.1 brief:

  1. action_confirm creates the project.task spine on first confirm.
  2. action_backfill_kitchen_task picks up legacy orphan orders.
  3. Double-confirming an order is idempotent — never spawns two tasks.
  4. mrp.production rows whose origin = SO.name and project_task_id =
     False get backlinked to the new task at spine-creation time.
  5. _cron_recompute_readiness_all stamps readiness_last_recomputed_at
     on every open kitchen task.

These tests run in @tagged('post_install', '-at_install') because the
spine creator depends on southbrook_project (for x_southbrook_sale_order_id)
and southbrook_project_mrp (for the readiness compute) — both have to
be installed first.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "premium_orchestration")
class TestPhase1Spine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Phase1 Test Customer",
        })
        cls.project = cls.env["project.project"].create({
            "name": "Phase1 Kitchen Jobs",
        })
        # Wire the config-param so the spine creator finds our project
        # rather than the first project in the DB (which on a fresh
        # CE install would be the "Internal" project).
        cls.env["ir.config_parameter"].sudo().set_param(
            "southbrook_premium.default_kitchen_project_id",
            str(cls.project.id),
        )

        # Two stages so we can assert the spine lands in Design & Quote
        # specifically (not just "the first stage").
        cls.stage_design = cls.env["project.task.type"].create({
            "name": "Design & Quote",
            "sequence": 1,
            "project_ids": [(4, cls.project.id)],
        })
        cls.stage_cutting = cls.env["project.task.type"].create({
            "name": "Cutting & Machining",
            "sequence": 2,
            "project_ids": [(4, cls.project.id)],
        })

        # A manufacturable kitchen product whose name carries the
        # heuristic markers the spec inference scans for.
        cls.kitchen_product = cls.env["product.product"].create({
            "name": "Base Cabinet, Shaker Maple, 30W",
            "type": "consu",
            "is_storable": True,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_so(self, name=None, confirmed=False):
        vals = {
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.kitchen_product.id,
                "product_uom_qty": 1.0,
            })],
        }
        if name:
            vals["client_order_ref"] = name
        so = self.env["sale.order"].create(vals)
        if confirmed:
            so.action_confirm()
        return so

    def _task_for(self, so):
        """Resolve the task for an order via the reverse-side link."""
        return self.env["project.task"].search(
            [("x_southbrook_sale_order_id", "=", so.id)])

    # ------------------------------------------------------------------
    # AC-1 — action_confirm creates the spine
    # ------------------------------------------------------------------
    def test_action_confirm_creates_project_task(self):
        so = self._make_so()
        self.assertFalse(self._task_for(so),
            "no task should exist before confirm")

        so.action_confirm()

        task = self._task_for(so)
        self.assertEqual(len(task), 1,
            "action_confirm must create exactly one project.task spine")
        self.assertEqual(task.project_id, self.project,
            "task must attach to the config-param project")
        self.assertEqual(task.stage_id, self.stage_design,
            "task must land in the Design & Quote stage")
        self.assertTrue(so.x_premium_orchestration_managed,
            "managed flag must flip True after spine creation")

    # ------------------------------------------------------------------
    # AC-2 — backfill rescues orphan orders
    # ------------------------------------------------------------------
    def test_backfill_creates_task_for_orphan_orders(self):
        # Simulate the production state: confirm 3 orders, then nuke
        # the tasks the auto-spine created. The legitimate way to
        # reproduce the "8 orphan orders" pathology is to wipe the
        # backlink in setup, then call backfill.
        orders = self.env["sale.order"]
        for _ in range(3):
            orders |= self._make_so(confirmed=True)
        for so in orders:
            existing = self._task_for(so)
            existing.unlink()
            so.x_premium_orchestration_managed = False

        # Sanity check: all 3 are orphans now.
        for so in orders:
            self.assertFalse(self._task_for(so))

        orders.action_backfill_kitchen_task()

        for so in orders:
            task = self._task_for(so)
            self.assertEqual(len(task), 1,
                "backfill must create exactly one task per orphan order")
            self.assertTrue(so.x_premium_orchestration_managed)

    # ------------------------------------------------------------------
    # AC-3 — double confirm is idempotent
    # ------------------------------------------------------------------
    def test_double_confirm_idempotent(self):
        so = self._make_so()
        so.action_confirm()
        # Calling the helper a second time must not double-create.
        # action_confirm itself can't be called twice on a confirmed SO
        # (state guard), so we exercise the private path the helper
        # uses internally.
        so._create_kitchen_project_task()
        so._create_kitchen_project_task()
        tasks = self._task_for(so)
        self.assertEqual(len(tasks), 1,
            "the spine creator must be idempotent across repeated calls")

    # ------------------------------------------------------------------
    # AC-4 — orphan MOs get backlinked
    # ------------------------------------------------------------------
    def test_orphan_mos_get_backlinked(self):
        # Build the order WITHOUT confirming it, then hand-create an MO
        # with origin = SO.name and project_task_id = False — exactly
        # the shape the 8 orphan MOs have on production.
        so = self._make_so()
        # Confirm to lock in the SO.name (draft SOs read as "New").
        so.action_confirm()
        # Nuke the auto-spine so we can re-create explicitly and
        # observe the backlink wiring.
        self._task_for(so).unlink()

        orphan_mo = self.env["mrp.production"].create({
            "product_id": self.kitchen_product.id,
            "product_qty": 1.0,
            "origin": so.name,
        })
        self.assertFalse(orphan_mo.project_task_id,
            "the MO must start orphan")

        so._create_kitchen_project_task()

        task = self._task_for(so)
        self.assertTrue(task, "spine must exist after _create call")
        orphan_mo.invalidate_recordset()
        self.assertEqual(orphan_mo.project_task_id, task,
            "orphan MO with matching origin must be backlinked")

    # ------------------------------------------------------------------
    # AC-5 — readiness cron stamps the timestamp
    # ------------------------------------------------------------------
    def test_recompute_readiness_cron(self):
        so = self._make_so(confirmed=True)
        task = self._task_for(so)
        self.assertTrue(task,
            "precondition: the SO must have spawned a task at confirm time")
        # Belt-and-braces: ensure the stamp starts empty.
        task.readiness_last_recomputed_at = False

        self.env["project.task"]._cron_recompute_readiness_all()

        task.invalidate_recordset()
        self.assertTrue(task.readiness_last_recomputed_at,
            "the cron must stamp readiness_last_recomputed_at on every "
            "open kitchen task")
