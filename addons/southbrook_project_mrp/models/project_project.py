# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    southbrook_job_count = fields.Integer(
        string="Manufacturing Jobs", compute="_compute_southbrook_mission_control")
    southbrook_active_mo_count = fields.Integer(
        string="Active MOs", compute="_compute_southbrook_mission_control")
    southbrook_ready_job_count = fields.Integer(
        string="Ready Jobs", compute="_compute_southbrook_mission_control")
    southbrook_blocked_job_count = fields.Integer(
        string="Blocked Jobs", compute="_compute_southbrook_mission_control")
    southbrook_review_job_count = fields.Integer(
        string="Review Jobs", compute="_compute_southbrook_mission_control")
    southbrook_at_risk_job_count = fields.Integer(
        string="At-Risk Jobs", compute="_compute_southbrook_mission_control")
    southbrook_material_risk_count = fields.Integer(
        string="Material Risk", compute="_compute_southbrook_mission_control")
    southbrook_cad_cutlist_job_count = fields.Integer(
        string="Needs CAD / Cutlist",
        compute="_compute_southbrook_mission_control")
    southbrook_unscheduled_wo_count = fields.Integer(
        string="Unscheduled WOs", compute="_compute_southbrook_mission_control")
    southbrook_unscheduled_job_count = fields.Integer(
        string="Unscheduled Jobs", compute="_compute_southbrook_mission_control")
    southbrook_can_start_today_wo_count = fields.Integer(
        string="Can Start Today",
        compute="_compute_southbrook_mission_control")
    southbrook_crew_gap_count = fields.Integer(
        string="Crew Gaps", compute="_compute_southbrook_mission_control")
    southbrook_install_risk_job_count = fields.Integer(
        string="Install Risk",
        compute="_compute_southbrook_mission_control")
    southbrook_equipment_blocked_count = fields.Integer(
        string="Equipment Blocks", compute="_compute_southbrook_mission_control")
    southbrook_over_capacity_count = fields.Integer(
        string="Over Capacity", compute="_compute_southbrook_mission_control")
    southbrook_job_cost_total = fields.Monetary(
        string="MO Job Cost", compute="_compute_southbrook_mission_control",
        currency_field="currency_id")
    southbrook_intelligence_prompt = fields.Char(
        string="Manufacturing Prompt", compute="_compute_southbrook_mission_control")
    southbrook_intelligence_severity = fields.Selection(
        [
            ("neutral", "Neutral"),
            ("info", "Info"),
            ("success", "Ready"),
            ("warning", "Review"),
            ("danger", "Stop"),
        ],
        string="Manufacturing Severity",
        compute="_compute_southbrook_mission_control",
    )

    @api.depends(
        "task_ids.production_count",
        "task_ids.job_at_risk",
        "task_ids.components_available",
        "task_ids.workorder_count",
        "task_ids.unscheduled_workorder_count",
        "task_ids.workorder_ids.southbrook_can_start_today",
        "task_ids.crew_gap",
        "task_ids.job_industrial_cost",
        "task_ids.material_at_risk",
        "task_ids.cad_cutlist_review_required",
        "task_ids.install_date_missing",
        "task_ids.equipment_blocked",
        "task_ids.workcenter_over_capacity",
    )
    def _compute_southbrook_mission_control(self):
        Task = self.env["project.task"]
        for project in self:
            tasks = Task.search([("project_id", "=", project.id)]).filtered(
                lambda task: task.production_count > 0)
            project.southbrook_job_count = len(tasks)
            project.southbrook_active_mo_count = sum(tasks.mapped("production_count"))
            project.southbrook_ready_job_count = len(tasks.filtered(
                lambda task: task.components_available == "ready"
                and not task.job_at_risk
                and not task.material_at_risk
                and not task.equipment_blocked
            ))
            project.southbrook_blocked_job_count = len(tasks.filtered(
                lambda task: task.manufacturing_readiness_state == "blocked"))
            project.southbrook_review_job_count = len(tasks.filtered(
                lambda task: task.manufacturing_readiness_state == "review"))
            project.southbrook_at_risk_job_count = len(tasks.filtered("job_at_risk"))
            project.southbrook_material_risk_count = len(tasks.filtered("material_at_risk"))
            project.southbrook_cad_cutlist_job_count = len(tasks.filtered(
                "cad_cutlist_review_required"))
            project.southbrook_unscheduled_wo_count = sum(
                tasks.mapped("unscheduled_workorder_count"))
            project.southbrook_unscheduled_job_count = len(tasks.filtered(
                lambda task: task.unscheduled_workorder_count > 0))
            project.southbrook_can_start_today_wo_count = len(
                tasks.mapped("workorder_ids").filtered(
                    "southbrook_can_start_today"))
            project.southbrook_crew_gap_count = len(tasks.filtered("crew_gap"))
            project.southbrook_install_risk_job_count = len(tasks.filtered(
                "install_date_missing"))
            project.southbrook_equipment_blocked_count = len(tasks.filtered("equipment_blocked"))
            project.southbrook_over_capacity_count = len(tasks.filtered("workcenter_over_capacity"))
            project.southbrook_job_cost_total = sum(tasks.mapped("job_industrial_cost"))
            severity, prompt = project._southbrook_pick_mission_prompt()
            project.southbrook_intelligence_severity = severity
            project.southbrook_intelligence_prompt = prompt

    def _southbrook_pick_mission_prompt(self):
        self.ensure_one()
        if not self.southbrook_job_count:
            return "neutral", "No manufacturing jobs yet"
        if self.southbrook_equipment_blocked_count:
            return "danger", "Stop: equipment blocked on %d job(s)" % (
                self.southbrook_equipment_blocked_count,)
        if self.southbrook_material_risk_count:
            return "danger", "Stop: material shortfall on %d job(s)" % (
                self.southbrook_material_risk_count,)
        if self.southbrook_at_risk_job_count:
            return "warning", "Review: %d job(s) at risk" % (
                self.southbrook_at_risk_job_count,)
        if self.southbrook_unscheduled_wo_count:
            return "warning", "Review: %d WO(s) need planned start" % (
                self.southbrook_unscheduled_wo_count,)
        if self.southbrook_crew_gap_count:
            return "warning", "Review: crew gap on %d job(s)" % (
                self.southbrook_crew_gap_count,)
        if self.southbrook_over_capacity_count:
            return "warning", "Review: work-center load over capacity on %d job(s)" % (
                self.southbrook_over_capacity_count,)
        return "success", "Clear: material, crew, and equipment ready"

    def action_southbrook_open_manufacturing_jobs(self):
        self.ensure_one()
        task_ids = self.env["project.task"].search(
            [("project_id", "=", self.id)]).filtered(
                lambda task: task.production_count > 0).ids
        return {
            "type": "ir.actions.act_window",
            "name": "Manufacturing Jobs - %s" % self.display_name,
            "res_model": "project.task",
            "domain": [("id", "in", task_ids)],
            "view_mode": "kanban,list,form",
            "context": {"create": False},
        }

    def _southbrook_readiness_action(self, state, label):
        self.ensure_one()
        tasks = self.env["project.task"].search([
            ("project_id", "=", self.id),
            ("manufacturing_readiness_state", "=", state),
        ]).filtered(lambda task: task.production_count > 0)
        return {
            "type": "ir.actions.act_window",
            "name": "%s - %s" % (label, self.display_name),
            "res_model": "project.task",
            "domain": [("id", "in", tasks.ids)],
            "view_mode": "list,form,kanban",
            "context": {
                "create": False,
                "search_default_group_manufacturing_readiness": 1,
            },
        }

    def action_southbrook_open_blocked_manufacturing_jobs(self):
        return self._southbrook_readiness_action(
            "blocked", "Blocked Manufacturing Jobs")

    def action_southbrook_open_review_manufacturing_jobs(self):
        return self._southbrook_readiness_action(
            "review", "Manufacturing Jobs Needing Review")

    def action_southbrook_open_ready_manufacturing_jobs(self):
        return self._southbrook_readiness_action(
            "ready", "Ready Manufacturing Jobs")

    def action_southbrook_open_unscheduled_manufacturing_jobs(self):
        self.ensure_one()
        tasks = self.env["project.task"].search(
            [("project_id", "=", self.id)]).filtered(
                lambda task: task.production_count > 0
                and task.unscheduled_workorder_count > 0)
        return {
            "type": "ir.actions.act_window",
            "name": "Scheduling Queue - %s" % self.display_name,
            "res_model": "project.task",
            "domain": [("id", "in", tasks.ids)],
            "view_mode": "list,form,kanban",
            "context": {
                "create": False,
                "search_default_manufacturing_blocked": 1,
            },
        }

    def action_southbrook_open_workorders_can_start_today(self):
        self.ensure_one()
        tasks = self.env["project.task"].search([
            ("project_id", "=", self.id),
        ]).filtered(lambda task: task.production_count > 0)
        workorders = tasks.mapped("workorder_ids").filtered(
            "southbrook_can_start_today")
        return {
            "type": "ir.actions.act_window",
            "name": "Can Start Today - %s" % self.display_name,
            "res_model": "mrp.workorder",
            "domain": [("id", "in", workorders.ids)],
            "view_mode": "list,form,gantt,calendar",
            "context": {"create": False},
        }

    def _southbrook_project_task_queue_action(self, tasks, label, context=None):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "%s - %s" % (label, self.display_name),
            "res_model": "project.task",
            "domain": [("id", "in", tasks.ids)],
            "view_mode": "list,form,kanban",
            "context": context or {"create": False},
        }

    def action_southbrook_open_cad_cutlist_jobs(self):
        self.ensure_one()
        tasks = self.env["project.task"].search(
            [("project_id", "=", self.id)]).filtered(
                lambda task: task.production_count > 0
                and task.cad_cutlist_review_required)
        return self._southbrook_project_task_queue_action(
            tasks,
            "Needs CAD / Cutlist",
            {"create": False, "search_default_needs_cad_cutlist": 1},
        )

    def action_southbrook_open_crew_gap_jobs(self):
        self.ensure_one()
        tasks = self.env["project.task"].search(
            [("project_id", "=", self.id)]).filtered(
                lambda task: task.production_count > 0 and task.crew_gap)
        return self._southbrook_project_task_queue_action(
            tasks,
            "Needs Crew",
            {"create": False, "search_default_needs_crew": 1},
        )

    def action_southbrook_open_install_risk_jobs(self):
        self.ensure_one()
        tasks = self.env["project.task"].search(
            [("project_id", "=", self.id)]).filtered(
                lambda task: task.production_count > 0
                and task.install_date_missing)
        return self._southbrook_project_task_queue_action(
            tasks,
            "Install Risk",
            {"create": False, "search_default_install_date_missing": 1},
        )

    def action_southbrook_open_equipment_blocked_jobs(self):
        self.ensure_one()
        tasks = self.env["project.task"].search(
            [("project_id", "=", self.id)]).filtered(
                lambda task: task.production_count > 0
                and task.equipment_blocked)
        return self._southbrook_project_task_queue_action(
            tasks,
            "Equipment Blocked",
            {"create": False, "search_default_equipment_blocked": 1},
        )

    def action_southbrook_open_over_capacity_jobs(self):
        self.ensure_one()
        tasks = self.env["project.task"].search(
            [("project_id", "=", self.id)]).filtered(
                lambda task: task.production_count > 0
                and task.workcenter_over_capacity)
        return self._southbrook_project_task_queue_action(
            tasks,
            "Over Capacity",
            {"create": False, "search_default_over_capacity": 1},
        )

    def action_southbrook_open_material_risk_jobs(self):
        self.ensure_one()
        tasks = self.env["project.task"].search(
            [("project_id", "=", self.id)]).filtered(
                lambda task: task.production_count > 0
                and task.material_at_risk)
        return {
            "type": "ir.actions.act_window",
            "name": "Material Risk Jobs - %s" % self.display_name,
            "res_model": "project.task",
            "domain": [("id", "in", tasks.ids)],
            "view_mode": "list,form,kanban",
            "context": {
                "create": False,
                "search_default_manufacturing_blocked": 1,
            },
        }

    def _southbrook_data_quality_line(self, issue_key, severity, record, reason,
                                      recommended_action):
        return {
            "issue_key": issue_key,
            "severity": severity,
            "model_name": record._name,
            "record_ref": record.display_name,
            "reason": reason,
            "recommended_action": recommended_action,
        }

    def action_southbrook_data_quality_dry_run(self):
        self.ensure_one()
        Report = self.env["southbrook.project.data.quality.report"]
        Line = self.env["southbrook.project.data.quality.line"]
        Task = self.env["project.task"]
        Production = self.env["mrp.production"]

        tasks = Task.search([("project_id", "=", self.id)])
        manufacturing_tasks = tasks.filtered(lambda task: task.production_count > 0)
        lines = []

        orphan_mos = Production.search([
            ("project_task_id", "=", False),
            ("state", "not in", ("done", "cancel")),
        ])
        for mo in orphan_mos:
            lines.append(self._southbrook_data_quality_line(
                "blank_kitchen_project",
                "warning",
                mo,
                "Manufacturing order has no linked kitchen job.",
                "Link the MO to the correct Project kitchen job; do not delete it.",
            ))

        for task in manufacturing_tasks:
            if not task.job_install_due:
                lines.append(self._southbrook_data_quality_line(
                    "missing_install_due",
                    "warning",
                    task,
                    "Kitchen job has linked MOs but no surfaced install due date.",
                    "Confirm the install due date on the source MO/order data.",
                ))
            if not task.job_estimated_cost:
                lines.append(self._southbrook_data_quality_line(
                    "placeholder_estimated_cost",
                    "info",
                    task,
                    "Estimated job cost is 0.00.",
                    "Review product standard costs or costing setup before using cost reports.",
                ))
            if (
                task.manufacturing_readiness_state == "ready"
                and (task.job_at_risk or task.material_at_risk
                     or task.equipment_blocked)
            ):
                lines.append(self._southbrook_data_quality_line(
                    "queue_overlap",
                    "blocker",
                    task,
                    "Job appears ready while risk/blocker flags are active.",
                    "Review readiness rules and the underlying job blockers.",
                ))
            if task.equipment_blocked != bool(task.maintenance_request_count):
                lines.append(self._southbrook_data_quality_line(
                    "equipment_count_mismatch",
                    "warning",
                    task,
                    "Equipment blocked flag and maintenance count disagree.",
                    "Recompute equipment readiness and inspect work-center equipment links.",
                ))

        if "stock.scrap" in self.env:
            Scrap = self.env["stock.scrap"]
            for scrap in Scrap.search([]).filtered(
                lambda rec: "REF" in (rec.display_name or "").upper()):
                lines.append(self._southbrook_data_quality_line(
                    "demo_scrap_unbuild",
                    "info",
                    scrap,
                    "Scrap record looks like demo/reference data.",
                    "Archive, tag, or exclude confirmed demo data; do not delete by default.",
                ))

        if "mrp.unbuild" in self.env:
            Unbuild = self.env["mrp.unbuild"]
            for unbuild in Unbuild.search([]).filtered(
                lambda rec: "REF" in (rec.display_name or "").upper()):
                lines.append(self._southbrook_data_quality_line(
                    "demo_scrap_unbuild",
                    "info",
                    unbuild,
                    "Unbuild/remake record looks like demo/reference data.",
                    "Archive, tag, or exclude confirmed demo data; do not delete by default.",
                ))

        report = Report.create({
            "project_id": self.id,
            "summary": (
                "Dry run found %d data-quality issue(s). No production data "
                "was changed." % len(lines)
            ),
        })
        for values in lines:
            values["report_id"] = report.id
        if lines:
            Line.create(lines)
        return {
            "type": "ir.actions.act_window",
            "name": "Southbrook Data Quality Dry Run",
            "res_model": "southbrook.project.data.quality.report",
            "res_id": report.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": False},
        }
