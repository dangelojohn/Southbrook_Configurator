# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields
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
        mo.action_confirm()
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
        self.assertIn("customer_id", list_view.arch_db)
        self.assertIn("install_due_date", list_view.arch_db)
        self.assertIn("risk_level", list_view.arch_db)
        self.assertIn("top_blocker", list_view.arch_db)
        self.assertIn("next_best_action", list_view.arch_db)

    def test_project_task_form_has_phase1_command_center_fields(self):
        view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        arch = view.arch_db
        self.assertIn("readiness_decision", arch)
        self.assertIn("readiness_score", arch)
        self.assertIn("risk_level", arch)
        self.assertIn("top_blocker", arch)
        self.assertIn("next_best_action", arch)
        self.assertIn("manufacturing_reality", arch)

    def test_phase1_context_fields_reuse_existing_job_sources(self):
        stage = self.env["project.task.type"].create({
            "name": "Assembly",
            "project_ids": [(4, self.project.id)],
        })
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.fp.id,
                "product_uom_qty": 1.0,
            })],
        })
        task = self.env["project.task"].create({
            "name": "Context Job",
            "project_id": self.project.id,
            "stage_id": stage.id,
            "x_southbrook_sale_order_id": so.id,
        })
        wc = self.env["mrp.workcenter"].create({"name": "Panel Saw"})
        mo = self._make_mo()
        mo.project_task_id = task.id
        self.env["mrp.workorder"].create({
            "name": "Cut panels",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "duration_expected": 45.0,
        })

        task.invalidate_recordset()

        self.assertEqual(task.source_order_id, so)
        self.assertEqual(task.source_order_name, so.name)
        self.assertEqual(task.customer_id, self.partner)
        self.assertEqual(task.pm_phase, "Assembly")
        self.assertEqual(task.linked_mo_count, 1)
        self.assertEqual(task.linked_wo_count, 1)
        self.assertEqual(task.unscheduled_wo_count, 1)
        self.assertEqual(task.current_bottleneck_workcenter_id, wc)
        self.assertEqual(task.readiness_decision, task.manufacturing_readiness_state)
        self.assertEqual(task.readiness_score, task.manufacturing_readiness_score)
        self.assertIn("Confirmed", task.manufacturing_reality)
        self.assertIn("1 WOs / 1 not scheduled", task.manufacturing_reality)
        self.assertIn("base", task.cabinet_family_summary.lower())

    def test_phase1_risk_blocker_and_next_action_are_plain_language(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.fp.id,
                "product_uom_qty": 1.0,
            })],
        })
        task = self.env["project.task"].create({
            "name": "Action Job",
            "project_id": self.project.id,
            "x_southbrook_sale_order_id": so.id,
        })
        wc = self.env["mrp.workcenter"].create({"name": "CNC Nesting"})
        mo = self._make_mo()
        mo.project_task_id = task.id
        self.env["mrp.workorder"].create({
            "name": "Nest panels",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "duration_expected": 30.0,
        })

        task.invalidate_recordset()

        self.assertIn(task.risk_level, ("high", "critical"))
        self.assertTrue(task.risk_reason)
        self.assertTrue(task.top_blocker)
        self.assertRegex(task.next_best_action, r"(Resolve|Schedule|Assign|Approve)")

    def test_phase2_readiness_lines_explain_unscheduled_job(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.fp.id,
                "product_uom_qty": 1.0,
            })],
        })
        task = self.env["project.task"].create({
            "name": "Evidence Job",
            "project_id": self.project.id,
            "x_southbrook_sale_order_id": so.id,
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
        task.action_recompute_readiness_lines()

        scheduling = task.readiness_line_ids.filtered(
            lambda line: line.check_key == "scheduling")
        self.assertEqual(len(scheduling), 1)
        self.assertEqual(scheduling.status, "blocked")
        self.assertEqual(scheduling.severity, "blocker")
        self.assertIn("not scheduled", scheduling.reason)
        self.assertIn("1 WOs / 1 not scheduled", scheduling.evidence)
        self.assertIn("Schedule", scheduling.recommended_action)

    def test_phase2_score_caps_unscheduled_job(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.fp.id,
                "product_uom_qty": 1.0,
            })],
        })
        task = self.env["project.task"].create({
            "name": "Capped Job",
            "project_id": self.project.id,
            "x_southbrook_sale_order_id": so.id,
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
        self.assertLessEqual(task.manufacturing_readiness_score, 55)
        self.assertLessEqual(task.readiness_score, 55)

    def test_phase2_no_linked_mos_caps_score_and_blocks(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.fp.id,
                "product_uom_qty": 1.0,
            })],
        })
        task = self.env["project.task"].create({
            "name": "No MO Job",
            "project_id": self.project.id,
            "x_southbrook_sale_order_id": so.id,
        })

        task.invalidate_recordset()
        task.action_recompute_readiness_lines()

        self.assertEqual(task.manufacturing_readiness_state, "blocked")
        self.assertLessEqual(task.manufacturing_readiness_score, 40)
        mrp_line = task.readiness_line_ids.filtered(
            lambda line: line.check_key == "mrp")
        self.assertEqual(len(mrp_line), 1)
        self.assertEqual(mrp_line.status, "blocked")
        self.assertIn("No linked manufacturing orders", mrp_line.reason)

    def test_phase2_readiness_line_action_opens_evidence(self):
        task = self.env["project.task"].create({
            "name": "Evidence Action Job",
            "project_id": self.project.id,
        })

        action = task.action_view_readiness_lines()

        self.assertEqual(action["res_model"], "southbrook.project.readiness.line")
        self.assertEqual(action["domain"], [("task_id", "=", task.id)])
        self.assertTrue(task.readiness_line_ids)
        view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        self.assertIn("action_view_readiness_lines", view.arch_db)
        self.assertIn("readiness_line_ids", view.arch_db)

    def test_phase3_production_control_queue_filters(self):
        search_view = self.env.ref(
            "southbrook_project_mrp.project_task_search_readiness")
        list_view = self.env.ref(
            "southbrook_project_mrp.project_task_list_readiness")

        for token in (
            "needs_cad_cutlist",
            "needs_scheduling",
            "needs_crew",
            "install_date_missing",
            "late_at_risk",
            "pm_stage_mismatch",
            "needs_materials",
            "equipment_blocked",
            "over_capacity",
            "group_customer",
            "group_source_order",
            "group_pm_phase",
        ):
            self.assertIn(token, search_view.arch_db)
        self.assertIn("cad_cutlist_review_required", list_view.arch_db)
        self.assertIn("install_date_missing", list_view.arch_db)
        self.assertIn("pm_stage_mismatch", list_view.arch_db)

    def test_phase3_queue_flags_surface_cad_install_and_stage_mismatch(self):
        stage = self.env["project.task.type"].create({
            "name": "Assembly",
            "project_ids": [(4, self.project.id)],
        })
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.fp.id,
                "product_uom_qty": 1.0,
            })],
        })
        task = self.env["project.task"].create({
            "name": "Queue Flag Job",
            "project_id": self.project.id,
            "stage_id": stage.id,
            "x_southbrook_sale_order_id": so.id,
        })
        mo = self._make_mo()
        mo.action_confirm()
        if "x_cad_status" in mo._fields:
            mo.x_cad_status = "pending"
        mo.project_task_id = task.id

        task.invalidate_recordset()

        if "x_cad_status" in mo._fields:
            self.assertTrue(task.cad_cutlist_review_required)
        self.assertTrue(task.install_date_missing)
        self.assertTrue(task.pm_stage_mismatch)

    def test_phase4_workorder_can_start_today_requires_schedule_crew_and_components(self):
        task = self.env["project.task"].create({
            "name": "Today Work Job",
            "project_id": self.project.id,
        })
        wc = self.env["mrp.workcenter"].create({"name": "Panel Saw"})
        mo = self._make_mo()
        mo.project_task_id = task.id
        mo.user_id = self.env.user.id
        wo = self.env["mrp.workorder"].create({
            "name": "Cut panels",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "date_start": fields.Datetime.now(),
            "duration_expected": 12.0,
        })

        task.invalidate_recordset()
        wo.invalidate_recordset()

        if mo.reservation_state != "assigned":
            self.assertFalse(wo.southbrook_can_start_today)
            self.assertIn("components", wo.southbrook_start_blocker.lower())
        else:
            self.assertTrue(wo.southbrook_can_start_today)
            self.assertEqual(wo.southbrook_start_blocker, "")

        wo.date_start = False
        wo.invalidate_recordset()
        self.assertFalse(wo.southbrook_can_start_today)
        self.assertIn("scheduled", wo.southbrook_start_blocker.lower())

    def test_phase4_project_action_opens_work_that_can_start_today(self):
        task = self.env["project.task"].create({
            "name": "Today Queue Job",
            "project_id": self.project.id,
        })
        wc = self.env["mrp.workcenter"].create({"name": "CNC Nesting"})
        mo = self._make_mo()
        mo.project_task_id = task.id
        mo.user_id = self.env.user.id
        wo = self.env["mrp.workorder"].create({
            "name": "Nest panels",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "date_start": fields.Datetime.now(),
            "duration_expected": 30.0,
        })

        action = task.action_view_workorders_can_start_today()

        self.assertEqual(action["res_model"], "mrp.workorder")
        if wo.southbrook_can_start_today:
            self.assertEqual(action["domain"], [("id", "in", [wo.id])])
        else:
            self.assertEqual(action["domain"], [("id", "in", [])])
        view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        self.assertIn("action_view_workorders_can_start_today", view.arch_db)
        self.assertIn("southbrook_can_start_today", view.arch_db)

    def test_project_form_has_readiness_job_actions(self):
        task = self.env["project.task"].create({
            "name": "Blocked Readiness Job",
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
        self.assertEqual(self.project.southbrook_blocked_job_count, 1)

        action = self.project.action_southbrook_open_blocked_manufacturing_jobs()

        self.assertEqual(action["res_model"], "project.task")
        self.assertEqual(action["domain"], [("id", "in", [task.id])])
        view = self.env.ref(
            "southbrook_project_mrp.project_project_form_readiness_actions")
        self.assertIn("action_southbrook_open_blocked_manufacturing_jobs", view.arch_db)
        self.assertIn("southbrook_blocked_job_count", view.arch_db)

    def test_project_form_has_scheduling_queue_action(self):
        task = self.env["project.task"].create({
            "name": "Scheduling Queue Job",
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
        self.assertEqual(self.project.southbrook_unscheduled_job_count, 1)

        action = self.project.action_southbrook_open_unscheduled_manufacturing_jobs()

        self.assertEqual(action["res_model"], "project.task")
        self.assertEqual(action["domain"], [("id", "in", [task.id])])
        view = self.env.ref(
            "southbrook_project_mrp.project_project_form_readiness_actions")
        self.assertIn(
            "action_southbrook_open_unscheduled_manufacturing_jobs", view.arch_db)
        self.assertIn("southbrook_unscheduled_job_count", view.arch_db)

    def test_project_form_has_material_risk_action(self):
        view = self.env.ref(
            "southbrook_project_mrp.project_project_form_readiness_actions")

        self.assertTrue(
            hasattr(self.project, "action_southbrook_open_material_risk_jobs"))
        self.assertIn(
            "action_southbrook_open_material_risk_jobs", view.arch_db)
        self.assertIn("southbrook_material_risk_count", view.arch_db)

    def test_phase4_project_form_has_can_start_today_queue(self):
        task = self.env["project.task"].create({
            "name": "Project Today Queue Job",
            "project_id": self.project.id,
        })
        wc = self.env["mrp.workcenter"].create({"name": "Edge Banding"})
        mo = self._make_mo()
        mo.project_task_id = task.id
        mo.user_id = self.env.user.id
        wo = self.env["mrp.workorder"].create({
            "name": "Band edges",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "date_start": fields.Datetime.now(),
            "duration_expected": 20.0,
        })

        self.project.invalidate_recordset()
        action = self.project.action_southbrook_open_workorders_can_start_today()

        self.assertEqual(action["res_model"], "mrp.workorder")
        if wo.southbrook_can_start_today:
            self.assertEqual(self.project.southbrook_can_start_today_wo_count, 1)
            self.assertEqual(action["domain"], [("id", "in", [wo.id])])
        else:
            self.assertEqual(self.project.southbrook_can_start_today_wo_count, 0)
            self.assertEqual(action["domain"], [("id", "in", [])])

        view = self.env.ref(
            "southbrook_project_mrp.project_project_form_readiness_actions")
        self.assertIn(
            "action_southbrook_open_workorders_can_start_today", view.arch_db)
        self.assertIn("southbrook_can_start_today_wo_count", view.arch_db)

    def test_phase4_project_form_has_cad_crew_install_queues(self):
        stage = self.env["project.task.type"].create({
            "name": "Assembly",
            "project_ids": [(4, self.project.id)],
        })
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.fp.id,
                "product_uom_qty": 1.0,
            })],
        })
        task = self.env["project.task"].create({
            "name": "Project Queue Job",
            "project_id": self.project.id,
            "stage_id": stage.id,
            "x_southbrook_sale_order_id": so.id,
        })
        wc = self.env["mrp.workcenter"].create({"name": "Assembly Bench"})
        mo = self._make_mo()
        mo.action_confirm()
        if "x_cad_status" in mo._fields:
            mo.x_cad_status = "pending"
        mo.project_task_id = task.id
        self.env["mrp.workorder"].create({
            "name": "Assemble case",
            "production_id": mo.id,
            "workcenter_id": wc.id,
            "duration_expected": 25.0,
        })

        self.project.invalidate_recordset()

        cad_action = self.project.action_southbrook_open_cad_cutlist_jobs()
        crew_action = self.project.action_southbrook_open_crew_gap_jobs()
        install_action = self.project.action_southbrook_open_install_risk_jobs()

        self.assertEqual(cad_action["res_model"], "project.task")
        self.assertEqual(crew_action["res_model"], "project.task")
        self.assertEqual(install_action["res_model"], "project.task")
        if "x_cad_status" in mo._fields:
            self.assertEqual(self.project.southbrook_cad_cutlist_job_count, 1)
            self.assertEqual(cad_action["domain"], [("id", "in", [task.id])])
        self.assertEqual(self.project.southbrook_crew_gap_count, 1)
        self.assertEqual(crew_action["domain"], [("id", "in", [task.id])])
        self.assertEqual(self.project.southbrook_install_risk_job_count, 1)
        self.assertEqual(install_action["domain"], [("id", "in", [task.id])])

        view = self.env.ref(
            "southbrook_project_mrp.project_project_form_readiness_actions")
        for token in (
            "action_southbrook_open_cad_cutlist_jobs",
            "action_southbrook_open_crew_gap_jobs",
            "action_southbrook_open_install_risk_jobs",
            "southbrook_cad_cutlist_job_count",
            "southbrook_crew_gap_count",
            "southbrook_install_risk_job_count",
        ):
            self.assertIn(token, view.arch_db)

    def test_phase4_project_form_has_equipment_and_capacity_queues(self):
        view = self.env.ref(
            "southbrook_project_mrp.project_project_form_readiness_actions")

        equipment_action = self.project.action_southbrook_open_equipment_blocked_jobs()
        capacity_action = self.project.action_southbrook_open_over_capacity_jobs()

        self.assertEqual(equipment_action["res_model"], "project.task")
        self.assertEqual(capacity_action["res_model"], "project.task")
        for token in (
            "action_southbrook_open_equipment_blocked_jobs",
            "action_southbrook_open_over_capacity_jobs",
            "southbrook_equipment_blocked_count",
            "southbrook_over_capacity_count",
        ):
            self.assertIn(token, view.arch_db)

    def test_phase5_cabinet_specs_participate_in_readiness(self):
        task = self.env["project.task"].create({
            "name": "Spec Readiness Job",
            "project_id": self.project.id,
        })

        task.invalidate_recordset()
        task.action_recompute_readiness_lines()

        specs = task.readiness_line_ids.filtered(
            lambda line: line.check_key == "cabinet_specs")
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs.status, "review")
        self.assertIn("Door style", specs.reason)
        self.assertIn("Confirm cabinet specs", specs.recommended_action)
        self.assertFalse(task.southbrook_specs_complete)

        task.write({
            "x_southbrook_material_species": "maple",
            "x_southbrook_hardware_specs": "Blum soft-close hinges and slides",
            "southbrook_door_style": "shaker",
            "southbrook_finish": "painted",
        })
        task.invalidate_recordset()
        task.action_recompute_readiness_lines()
        specs = task.readiness_line_ids.filtered(
            lambda line: line.check_key == "cabinet_specs")

        self.assertEqual(specs.status, "ready")
        self.assertTrue(task.southbrook_specs_complete)

    def test_phase5_cabinet_specs_are_on_command_center_views(self):
        form_view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        search_view = self.env.ref(
            "southbrook_project_mrp.project_task_search_readiness")

        for token in (
            "southbrook_project_mrp_cabinet_specs",
            "southbrook_door_style",
            "southbrook_finish",
            "southbrook_specs_complete",
        ):
            self.assertIn(token, form_view.arch_db)
        self.assertIn("missing_cabinet_specs", search_view.arch_db)

    def test_phase5_install_readiness_checklist_explains_missing_data(self):
        task = self.env["project.task"].create({
            "name": "Install Readiness Job",
            "project_id": self.project.id,
        })

        task.invalidate_recordset()
        task.action_recompute_readiness_lines()

        self.assertEqual(task.southbrook_install_readiness_state, "review")
        self.assertIn("Install due date", task.southbrook_install_readiness_reason)
        install_line = task.readiness_line_ids.filtered(
            lambda line: line.check_key == "install")
        self.assertEqual(len(install_line), 1)
        self.assertEqual(install_line.status, "review")
        self.assertIn("Install due date", install_line.reason)
        self.assertIn("Confirm install readiness", install_line.recommended_action)

        task.write({
            "southbrook_site_measurement_status": "received",
            "southbrook_delivery_address": "123 Job Site Road",
            "southbrook_install_contact": "Site Contact 555-0100",
            "southbrook_pack_label_complete": True,
            "southbrook_qc_complete": True,
            "southbrook_delivery_staged": True,
        })
        task.invalidate_recordset()

        if task.job_install_due:
            self.assertEqual(task.southbrook_install_readiness_state, "ready")
        else:
            self.assertEqual(task.southbrook_install_readiness_state, "review")
            self.assertIn("Install due date", task.southbrook_install_readiness_reason)

    def test_phase5_install_readiness_is_on_command_center_views(self):
        form_view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        search_view = self.env.ref(
            "southbrook_project_mrp.project_task_search_readiness")

        for token in (
            "southbrook_project_mrp_install_readiness",
            "southbrook_install_readiness_state",
            "southbrook_site_measurement_status",
            "southbrook_pack_label_complete",
            "southbrook_qc_complete",
            "southbrook_delivery_staged",
        ):
            self.assertIn(token, form_view.arch_db)
        self.assertIn("install_readiness_review", search_view.arch_db)

    def test_phase5_production_release_checklist_blocks_incomplete_jobs(self):
        task = self.env["project.task"].create({
            "name": "Release Checklist Job",
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

        task.action_recompute_readiness_lines()

        self.assertEqual(task.southbrook_production_release_state, "blocked")
        self.assertIn(
            "CAD approved", task.southbrook_production_release_reason)
        self.assertIn(
            "BoM verified", task.southbrook_production_release_reason)
        release_line = task.readiness_line_ids.filtered(
            lambda line: line.check_key == "production_release")
        self.assertEqual(len(release_line), 1)
        self.assertEqual(release_line.status, "blocked")
        self.assertIn("Schedule work orders", release_line.reason)

    def test_phase5_production_release_checklist_is_on_command_center_views(self):
        form_view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        search_view = self.env.ref(
            "southbrook_project_mrp.project_task_search_readiness")

        for token in (
            "southbrook_project_mrp_production_release",
            "southbrook_production_release_state",
            "southbrook_release_cad_approved",
            "southbrook_release_cutlist_approved",
            "southbrook_release_bom_verified",
            "southbrook_release_crew_reserved",
            "southbrook_release_equipment_available",
        ):
            self.assertIn(token, form_view.arch_db)
        self.assertIn("production_release_blocked", search_view.arch_db)

    def test_phase5_cabinet_family_progress_summarizes_mo_and_wo_state(self):
        task = self.env["project.task"].create({
            "name": "Family Progress Job",
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

        self.assertIn("Base", task.southbrook_cabinet_family_progress)
        self.assertIn("MOs 1", task.southbrook_cabinet_family_progress)
        self.assertIn("WOs 0/1 complete", task.southbrook_cabinet_family_progress)
        self.assertIn("Panel Saw", task.southbrook_cabinet_family_progress)
        self.assertIn("Schedule work orders", task.southbrook_cabinet_family_progress)

    def test_phase5_cabinet_family_progress_is_on_command_center_views(self):
        form_view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        list_view = self.env.ref("southbrook_project_mrp.project_task_list_readiness")

        self.assertIn("southbrook_cabinet_family_progress", form_view.arch_db)
        self.assertIn("southbrook_cabinet_family_progress", list_view.arch_db)

    def test_phase5_job_template_creates_cabinet_specific_subtasks(self):
        template = self.env.ref(
            "southbrook_project_mrp.job_template_full_kitchen")
        task = self.env["project.task"].create({
            "name": "Template Job",
            "project_id": self.project.id,
            "job_type": "full_kitchen",
            "southbrook_job_template_id": template.id,
        })

        task.action_apply_southbrook_job_template()
        child_names = set(task.child_ids.mapped("name"))

        self.assertIn("CAD / Cutlist Release", child_names)
        self.assertIn("Production Release Checklist", child_names)
        self.assertIn("Install Readiness", child_names)

        task.action_apply_southbrook_job_template()
        self.assertEqual(
            len(task.child_ids.filtered(
                lambda child: child.name == "CAD / Cutlist Release")),
            1,
        )

    def test_phase5_job_templates_are_loaded_and_visible_on_task_form(self):
        for xml_id in (
            "job_template_full_kitchen",
            "job_template_vanity",
            "job_template_pantry",
            "job_template_repair",
            "job_template_warranty_remake",
            "job_template_single_cabinet",
            "job_template_worktop",
        ):
            self.assertTrue(self.env.ref("southbrook_project_mrp.%s" % xml_id))

        form_view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")
        self.assertIn("southbrook_job_template_id", form_view.arch_db)
        self.assertIn("action_apply_southbrook_job_template", form_view.arch_db)

    def test_phase5_quality_summary_surfaces_deficiency_and_remake_tasks(self):
        task = self.env["project.task"].create({
            "name": "Quality Visibility Job",
            "project_id": self.project.id,
            "southbrook_install_deficiency_notes": "Replace damaged drawer front.",
        })
        self.env["project.task"].create({
            "name": "Remake drawer front",
            "project_id": self.project.id,
            "parent_id": task.id,
            "job_type": "warranty",
        })

        task.invalidate_recordset()

        self.assertEqual(task.southbrook_remake_task_count, 1)
        self.assertIn("Deficiency notes", task.southbrook_quality_issue_summary)
        self.assertIn("1 warranty/remake task", task.southbrook_quality_issue_summary)

        action = task.action_view_southbrook_remake_tasks()
        self.assertEqual(action["res_model"], "project.task")
        self.assertEqual(action["domain"], [("id", "in", task.child_ids.ids)])

    def test_phase5_quality_and_remake_visibility_is_on_command_center_views(self):
        form_view = self.env.ref("southbrook_project_mrp.project_task_form_mrp")

        for token in (
            "southbrook_project_mrp_quality_rework",
            "southbrook_quality_issue_summary",
            "southbrook_remake_task_count",
            "action_view_southbrook_remake_tasks",
            "action_view_southbrook_rework_workorders",
            "action_view_southbrook_scrap_records",
            "action_view_southbrook_unbuild_records",
        ):
            self.assertIn(token, form_view.arch_db)

    def test_phase6_data_quality_dry_run_reports_missing_install_and_zero_cost(self):
        task = self.env["project.task"].create({
            "name": "Cleanup Pilot Job",
            "project_id": self.project.id,
        })
        mo = self._make_mo()
        mo.project_task_id = task.id

        action = self.project.action_southbrook_data_quality_dry_run()
        report = self.env["southbrook.project.data.quality.report"].browse(
            action["res_id"])
        issue_keys = set(report.line_ids.mapped("issue_key"))

        self.assertIn("missing_install_due", issue_keys)
        self.assertIn("placeholder_estimated_cost", issue_keys)
        self.assertIn("Dry run", report.summary)
        self.assertEqual(action["res_model"], "southbrook.project.data.quality.report")

    def test_phase6_data_quality_report_views_are_available(self):
        project_form = self.env.ref(
            "southbrook_project_mrp.project_project_form_readiness_actions")
        report_form = self.env.ref(
            "southbrook_project_mrp.data_quality_report_form")

        self.assertIn("action_southbrook_data_quality_dry_run", project_form.arch_db)
        self.assertIn("line_ids", report_form.arch_db)
        self.assertIn("recommended_action", report_form.arch_db)
