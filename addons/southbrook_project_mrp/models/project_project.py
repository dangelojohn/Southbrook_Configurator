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
    southbrook_unscheduled_wo_count = fields.Integer(
        string="Unscheduled WOs", compute="_compute_southbrook_mission_control")
    southbrook_unscheduled_job_count = fields.Integer(
        string="Unscheduled Jobs", compute="_compute_southbrook_mission_control")
    southbrook_crew_gap_count = fields.Integer(
        string="Crew Gaps", compute="_compute_southbrook_mission_control")
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
        "task_ids.crew_gap",
        "task_ids.job_industrial_cost",
        "task_ids.material_at_risk",
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
            project.southbrook_unscheduled_wo_count = sum(
                tasks.mapped("unscheduled_workorder_count"))
            project.southbrook_unscheduled_job_count = len(tasks.filtered(
                lambda task: task.unscheduled_workorder_count > 0))
            project.southbrook_crew_gap_count = len(tasks.filtered("crew_gap"))
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
