# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "project_mrp")
class TestProjectMrpIntegration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Job Customer"})
        cls.project = cls.env["project.project"].create({"name": "Jobs"})
        # A manufacturable cabinetry-ish product (has a BoM => drives an MO).
        cls.comp = cls.env["product.product"].create(
            {"name": "Panel", "type": "consu", "is_storable": True})
        cls.fp = cls.env["product.product"].create({
            "name": "SB-BASE-1DR", "type": "consu", "is_storable": True})
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.fp.product_tmpl_id.id,
            "product_qty": 1.0,
            "bom_line_ids": [(0, 0, {"product_id": cls.comp.id,
                                     "product_qty": 1.0})],
        })

    def _make_mo(self):
        mo = self.env["mrp.production"].create(
            {"product_id": self.fp.id, "product_qty": 1.0, "bom_id": self.bom.id})
        return mo

    # --- T1.1 + T1.2 ---------------------------------------------------------
    def test_link_and_status_rollup(self):
        task = self.env["project.task"].create(
            {"name": "Smith Kitchen", "project_id": self.project.id})
        self.assertEqual(task.production_count, 0)
        self.assertEqual(task.components_available, "none")

        mo1, mo2 = self._make_mo(), self._make_mo()
        (mo1 | mo2).write({"project_task_id": task.id})
        task.invalidate_recordset()

        self.assertEqual(task.production_count, 2)
        self.assertEqual(set(task.production_ids.ids), {mo1.id, mo2.id})
        self.assertIn(mo1.name, task.mo_reference)
        self.assertIn("SB-BASE-1DR", task.mo_product_summary)
        self.assertTrue(task.mo_state_summary)              # non-empty rollup
        self.assertNotEqual(task.components_available, "none")

    # --- T1.3: sale confirm creates + links the job -------------------------
    def test_sale_confirm_creates_job(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "southbrook_project_mrp.job_project_id", str(self.project.id))
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.fp.id,
                                   "product_uom_qty": 1.0})],
        })
        self.assertFalse(self.env["project.task"].search(
            [("x_southbrook_sale_order_id", "=", so.id)]))

        so.action_confirm()

        job = self.env["project.task"].search(
            [("x_southbrook_sale_order_id", "=", so.id)])
        self.assertEqual(len(job), 1, "confirming a manufacturing sale must "
                                      "create exactly one job task")
        self.assertEqual(job.project_id, self.project)
        # Idempotent: re-confirm path doesn't double-create.
        so._southbrook_ensure_job()
        self.assertEqual(len(self.env["project.task"].search(
            [("x_southbrook_sale_order_id", "=", so.id)])), 1)

    def test_non_manufacturing_sale_makes_no_job(self):
        svc = self.env["product.product"].create(
            {"name": "Consulting", "type": "service"})
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": svc.id,
                                   "product_uom_qty": 1.0})],
        })
        so.action_confirm()
        self.assertFalse(self.env["project.task"].search(
            [("x_southbrook_sale_order_id", "=", so.id)]),
            "a sale with no BoM-able product should not create a job")

    # --- MO back-links to an existing job on create -------------------------
    def test_mo_create_backlinks_to_job(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {"product_id": self.fp.id,
                                   "product_uom_qty": 1.0})],
        })
        job = self.env["project.task"].create({
            "name": "Job", "project_id": self.project.id,
            "x_southbrook_sale_order_id": so.id})
        mo = self.env["mrp.production"].create({
            "product_id": self.fp.id, "product_qty": 1.0, "bom_id": self.bom.id,
            "sale_line_id": so.order_line[0].id})
        self.assertEqual(mo.project_task_id, job,
                         "an MO traced to a sale that has a job must back-link")

    # --- B2: cost rollup is non-zero on a costed MO -------------------------
    def test_b2_cost_rollup(self):
        self.fp.standard_price = 250.0
        task = self.env["project.task"].create(
            {"name": "Cost Job", "project_id": self.project.id})
        mo = self._make_mo()
        mo.product_qty = 2.0
        mo.project_task_id = task.id
        task.invalidate_recordset()
        # estimated = standard_price * qty = 250 * 2 = 500 (non-zero even uncosted)
        self.assertEqual(task.job_estimated_cost, 500.0)
        # actual industrial cost: costing module absent in test -> 0, no error
        self.assertEqual(task.job_industrial_cost, 0.0)

    # --- B3: at-risk + accurate aggregate -----------------------------------
    def test_b3_at_risk_and_aggregate(self):
        task = self.env["project.task"].create(
            {"name": "Risk Job", "project_id": self.project.id})
        mo = self._make_mo()
        mo.action_confirm()            # confirmed; components not reserved
        mo.project_task_id = task.id
        task.invalidate_recordset()
        self.assertNotEqual(task.components_available, "ready")
        self.assertTrue(task.job_at_risk)
        self.assertIn("waiting on components", task.job_risk_reason)
        self.assertIn("Confirmed", task.mo_state_summary)   # readable, not a count

    # --- B4: ECO soft-reference never crashes when southbrook.eco absent ----
    def test_b4_eco_soft(self):
        task = self.env["project.task"].create(
            {"name": "ECO Job", "project_id": self.project.id})
        self._make_mo().project_task_id = task.id
        task.invalidate_recordset()
        self.assertEqual(task.eco_count, 0)
        self.assertEqual(task.eco_pending_count, 0)

    # --- B5: stage <-> MO divergence is flagged -----------------------------
    def test_b5_stage_divergence(self):
        finishing = self.env["project.task.type"].create(
            {"name": "Finishing", "project_ids": [(4, self.project.id)]})
        task = self.env["project.task"].create({
            "name": "Stage Job", "project_id": self.project.id,
            "stage_id": finishing.id})
        mo = self._make_mo()
        mo.action_confirm()            # confirmed, not "started"
        mo.project_task_id = task.id
        task.invalidate_recordset()
        self.assertTrue(task.stage_mo_divergence)
        self.assertIn("Finishing", task.stage_mo_note)

    def test_workorder_not_scheduled_flag(self):
        task = self.env["project.task"].create(
            {"name": "WO Schedule Job", "project_id": self.project.id})
        wc = self.env["mrp.workcenter"].create({"name": "Panel Saw"})
        mo = self._make_mo()
        mo.project_task_id = task.id
        wo = self.env["mrp.workorder"].create({
            "name": "Cut panels",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "duration_expected": 12.0,
        })
        task.invalidate_recordset()
        self.assertTrue(wo.southbrook_not_scheduled)
        self.assertEqual(task.unscheduled_workorder_count, 1)

    def test_material_readiness_rollup(self):
        task = self.env["project.task"].create(
            {"name": "Material Job", "project_id": self.project.id})
        mo = self._make_mo()
        mo.project_task_id = task.id
        mo.invalidate_recordset()
        task.invalidate_recordset()
        self.assertEqual(task.production_count, 1)
        self.assertTrue(task.material_readiness_summary)
        self.assertEqual(
            task.material_ready_count
            + task.material_partial_count
            + task.material_unavailable_count,
            1,
        )

    def test_equipment_readiness_rollup(self):
        task = self.env["project.task"].create(
            {"name": "Equipment Job", "project_id": self.project.id})
        wc = self.env["mrp.workcenter"].create({"name": "CNC Nesting"})
        equipment = self.env["maintenance.equipment"].create({
            "name": "CNC Router",
            "workcenter_id": wc.id,
        })
        mo = self._make_mo()
        mo.project_task_id = task.id
        self.env["mrp.workorder"].create({
            "name": "Route parts",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "duration_expected": 18.0,
        })
        request = self.env["maintenance.request"].create({
            "name": "Spindle fault",
            "equipment_id": equipment.id,
        })
        task.invalidate_recordset()
        self.assertIn(request, task.maintenance_request_ids)
        self.assertTrue(task.equipment_blocked)
        self.assertIn("BLOCKED", task.equipment_readiness_summary)

    def test_project_manufacturing_summary_empty_project(self):
        project = self.env["project.project"].create({"name": "Empty Plant Board"})
        self.assertEqual(project.southbrook_job_count, 0)
        self.assertEqual(project.southbrook_active_mo_count, 0)
        self.assertEqual(project.southbrook_unscheduled_wo_count, 0)
        self.assertEqual(project.southbrook_intelligence_severity, "neutral")
        self.assertEqual(project.southbrook_intelligence_prompt, "No manufacturing jobs yet")

    def test_project_manufacturing_summary_from_job_tasks(self):
        task = self.env["project.task"].create({
            "name": "Mission Control Job",
            "project_id": self.project.id,
        })
        wc = self.env["mrp.workcenter"].create({"name": "Panel Saw"})
        mo = self._make_mo()
        mo.project_task_id = task.id
        self.env["mrp.workorder"].create({
            "name": "Cut panels",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "duration_expected": 12.0,
        })

        self.project.invalidate_recordset()
        self.assertEqual(self.project.southbrook_job_count, 1)
        self.assertEqual(self.project.southbrook_active_mo_count, 1)
        self.assertEqual(self.project.southbrook_unscheduled_wo_count, 1)
        self.assertEqual(self.project.southbrook_crew_gap_count, 1)
        self.assertEqual(self.project.southbrook_intelligence_severity, "warning")
        self.assertIn("planned start", self.project.southbrook_intelligence_prompt)

    def test_project_kanban_has_mission_control_fields(self):
        view = self.env.ref(
            "southbrook_project_mrp.project_project_kanban_mission_control")
        arch = view.arch_db
        self.assertIn("southbrook_intelligence_prompt", arch)
        self.assertIn("southbrook_unscheduled_wo_count", arch)
        self.assertIn("southbrook_equipment_blocked_count", arch)
        self.assertIn("action_southbrook_open_manufacturing_jobs", arch)

    def test_project_task_exposes_manufacturing_calculations(self):
        task = self.env["project.task"].create({
            "name": "Calculation Job",
            "project_id": self.project.id,
        })
        mo = self._make_mo()
        mo.project_task_id = task.id

        action = task.action_view_manufacturing_calculations()

        self.assertEqual(action["res_model"], "southbrook.mi.check")
        self.assertEqual(action["domain"], [("production_id", "in", [mo.id])])
        view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        self.assertIn("Calculations", view.arch_db)
        self.assertIn("action_view_manufacturing_calculations", view.arch_db)

    def test_manufacturing_readiness_decision_blocks_unscheduled_job(self):
        task = self.env["project.task"].create({
            "name": "Readiness Job",
            "project_id": self.project.id,
        })
        wc = self.env["mrp.workcenter"].create({"name": "Panel Saw"})
        mo = self._make_mo()
        mo.project_task_id = task.id
        self.env["mrp.workorder"].create({
            "name": "Cut panels",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "duration_expected": 12.0,
        })

        task.invalidate_recordset()

        self.assertEqual(task.manufacturing_readiness_state, "blocked")
        self.assertLess(task.manufacturing_readiness_score, 100)
        self.assertIn("Scheduling", task.manufacturing_blocker_summary)
        self.assertIn("not scheduled", task.manufacturing_blocker_summary)
        self.assertIn("Scheduling", task.manufacturing_waterfall_summary)

    def test_project_task_form_has_manufacturing_readiness_panel(self):
        view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        arch = view.arch_db
        self.assertIn("Manufacturing Readiness", arch)
        self.assertIn("manufacturing_readiness_score", arch)
        self.assertIn("manufacturing_waterfall_summary", arch)
        self.assertIn("manufacturing_blocker_summary", arch)

    def test_project_task_readiness_list_and_search_views(self):
        list_view = self.env.ref(
            "southbrook_project_mrp.project_task_list_readiness")
        search_view = self.env.ref(
            "southbrook_project_mrp.project_task_search_readiness")

        self.assertIn("manufacturing_readiness_state", list_view.arch_db)
        self.assertIn("manufacturing_readiness_score", list_view.arch_db)
        self.assertIn("manufacturing_blocked", search_view.arch_db)
        self.assertIn("manufacturing_review", search_view.arch_db)
        self.assertIn("manufacturing_ready", search_view.arch_db)
