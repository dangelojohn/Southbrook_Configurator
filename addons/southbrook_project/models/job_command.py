# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models

from .project_task import MATERIAL_SPECIES_SELECTION


JOB_TYPES = [
    ("kitchen", "Kitchen"),
    ("vanity", "Vanity"),
    ("repair", "Repair"),
    ("warranty", "Warranty"),
]

CHECKLIST_STATES = [
    ("ready", "Ready"),
    ("warning", "Warning"),
    ("blocked", "Blocked"),
]

SOUTHBROOK_ROLE_GROUPS = ",".join([
    "southbrook_project.group_southbrook_pm",
    "southbrook_project.group_southbrook_shop_lead",
    "southbrook_project.group_southbrook_designer",
    "southbrook_project.group_southbrook_installer",
    "southbrook_project.group_southbrook_executive",
    "base.group_system",
])

FAMILY_SELECTION = [
    ("base", "Base"),
    ("wall", "Wall"),
    ("tall", "Tall"),
    ("drawer", "Drawer"),
    ("sink", "Sink"),
    ("corner", "Corner"),
    ("vanity", "Vanity"),
    ("accessory", "Accessory"),
    ("worktop", "Worktop"),
]

GATE_SELECTION = [
    ("estimate", "Estimate"),
    ("engineering", "Engineering"),
    ("bom_cutlist", "BOM / Cutlist"),
    ("purchasing", "Purchasing"),
    ("materials", "Materials"),
    ("tooling", "Tooling"),
    ("labor", "Labor"),
    ("equipment", "Equipment"),
    ("schedule", "Production Schedule"),
    ("delivery", "Delivery"),
    ("install", "Install"),
]


class SouthbrookJobTemplate(models.Model):
    _name = "southbrook.job.template"
    _description = "Southbrook kitchen job template"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    job_type = fields.Selection(JOB_TYPES, required=True, default="kitchen")
    cabinet_family = fields.Selection(FAMILY_SELECTION, default="base")
    material_species = fields.Selection(MATERIAL_SPECIES_SELECTION)
    unit_count = fields.Integer(default=1)
    hardware_specs = fields.Text()
    checklist_template_ids = fields.One2many(
        "southbrook.job.template.line",
        "template_id",
        string="Checklist",
    )

    def action_create_project_job(self, project_id=False):
        self.ensure_one()
        if not project_id and self.env.context.get("active_model") == "project.project":
            project_id = self.env.context.get("active_id")
        project_id = project_id or self.env.context.get("default_project_id")
        project = self.env["project.project"].browse(project_id).exists()
        if not project:
            project = self.env["project.project"].search([
                ("name", "=", _("Southbrook Kitchen Jobs")),
            ], limit=1)
        if not project:
            project = self.env["project.project"].create({
                "name": _("Southbrook Kitchen Jobs"),
            })
        task = self.env["project.task"].create({
            "name": self.name,
            "project_id": project.id,
            "x_southbrook_job_type": self.job_type,
            "x_southbrook_cabinet_family": self.cabinet_family,
            "x_southbrook_material_species": self.material_species,
            "x_southbrook_unit_count": self.unit_count,
            "x_southbrook_hardware_specs": self.hardware_specs,
        })
        for line in self.checklist_template_ids.sorted("sequence"):
            self.env["southbrook.job.checklist.item"].create({
                "task_id": task.id,
                "name": line.name,
                "gate": line.gate,
                "required": line.required,
                "sequence": line.sequence,
            })
        task.action_southbrook_refresh_mrp_readiness_snapshot()
        return {
            "type": "ir.actions.act_window",
            "name": _("Kitchen Job"),
            "res_model": "project.task",
            "view_mode": "form",
            "res_id": task.id,
        }


class SouthbrookJobTemplateLine(models.Model):
    _name = "southbrook.job.template.line"
    _description = "Southbrook job template checklist line"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "southbrook.job.template",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(required=True)
    gate = fields.Selection(
        GATE_SELECTION,
        required=True,
        default="engineering",
    )
    required = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)


class SouthbrookJobChecklistItem(models.Model):
    _name = "southbrook.job.checklist.item"
    _description = "Southbrook job release checklist item"
    _order = "sequence, id"

    task_id = fields.Many2one(
        "project.task",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(required=True)
    gate = fields.Selection(
        GATE_SELECTION,
        required=True,
        default="engineering",
        index=True,
    )
    required = fields.Boolean(default=True)
    done = fields.Boolean(default=False, index=True)
    waived = fields.Boolean(default=False)
    sequence = fields.Integer(default=10)
    note = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        items = super().create(vals_list)
        items.mapped("task_id").action_southbrook_refresh_mrp_readiness_snapshot()
        return items

    def write(self, vals):
        tasks = self.mapped("task_id")
        res = super().write(vals)
        if {"done", "waived", "required", "gate", "name", "task_id"}.intersection(vals):
            tasks |= self.mapped("task_id")
            tasks.action_southbrook_refresh_mrp_readiness_snapshot()
        return res

    def unlink(self):
        tasks = self.mapped("task_id")
        res = super().unlink()
        tasks.action_southbrook_refresh_mrp_readiness_snapshot()
        return res


class ProjectTask(models.Model):
    _inherit = "project.task"

    x_southbrook_job_type = fields.Selection(
        JOB_TYPES,
        string="Job Type",
        index=True,
    )
    x_southbrook_cabinet_family = fields.Selection(
        FAMILY_SELECTION,
        string="Cabinet Family",
        index=True,
    )
    x_southbrook_install_due_date = fields.Date(
        string="Install Due",
        index=True,
    )
    x_southbrook_pm_phase = fields.Selection(
        [
            ("estimate", "Estimate"),
            ("engineering", "Engineering"),
            ("purchasing", "Purchasing"),
            ("production", "Production"),
            ("install", "Install"),
            ("closed", "Closed"),
        ],
        string="PM Phase",
        default="engineering",
        index=True,
    )
    x_southbrook_manufacturing_reality = fields.Selection(
        [
            ("no_mrp", "No MRP"),
            ("blocked", "Blocked"),
            ("ready", "Ready"),
            ("in_production", "In Production"),
            ("done", "Done"),
        ],
        string="Manufacturing Reality",
        compute="_compute_southbrook_job_command",
    )
    x_southbrook_checklist_item_ids = fields.One2many(
        "southbrook.job.checklist.item",
        "task_id",
        string="Release Checklist",
        groups=SOUTHBROOK_ROLE_GROUPS,
    )
    x_southbrook_checklist_state = fields.Selection(
        CHECKLIST_STATES,
        compute="_compute_southbrook_job_command",
        store=True,
        string="Checklist State",
        default="ready",
        index=True,
    )
    x_southbrook_checklist_summary = fields.Text(
        compute="_compute_southbrook_job_command",
        store=True,
        string="Checklist Summary",
        groups=SOUTHBROOK_ROLE_GROUPS,
    )
    x_southbrook_cabinet_spec_summary = fields.Text(
        compute="_compute_southbrook_job_command",
        string="Cabinet Spec Summary",
    )

    @api.depends(
        "x_southbrook_checklist_item_ids.done",
        "x_southbrook_checklist_item_ids.waived",
        "x_southbrook_checklist_item_ids.required",
        "x_southbrook_checklist_item_ids.name",
        "x_southbrook_cabinet_family",
        "x_southbrook_hardware_specs",
        "x_southbrook_job_type",
        "x_southbrook_material_species",
        "x_southbrook_readiness_state",
        "x_southbrook_unit_count",
    )
    def _compute_southbrook_job_command(self):
        material_labels = dict(self._fields["x_southbrook_material_species"].selection)
        family_labels = dict(FAMILY_SELECTION)
        job_type_labels = dict(JOB_TYPES)
        for task in self:
            checklist_items = task.sudo().x_southbrook_checklist_item_ids
            required_open = checklist_items.filtered(
                lambda item: item.required and not item.done and not item.waived
            )
            optional_open = checklist_items.filtered(
                lambda item: not item.required and not item.done and not item.waived
            )
            if required_open:
                task.x_southbrook_checklist_state = "blocked"
                task.x_southbrook_checklist_summary = "; ".join(
                    required_open[:3].mapped("name")
                )
            elif optional_open:
                task.x_southbrook_checklist_state = "warning"
                task.x_southbrook_checklist_summary = "; ".join(
                    optional_open[:3].mapped("name")
                )
            else:
                task.x_southbrook_checklist_state = "ready"
                task.x_southbrook_checklist_summary = _("Checklist complete.")

            if task.x_southbrook_readiness_state == "blocked":
                task.x_southbrook_manufacturing_reality = "blocked"
            elif task.x_southbrook_readiness_state == "ready":
                task.x_southbrook_manufacturing_reality = "ready"
            else:
                task.x_southbrook_manufacturing_reality = "no_mrp"

            pieces = [
                job_type_labels.get(task.x_southbrook_job_type),
                family_labels.get(task.x_southbrook_cabinet_family),
                material_labels.get(task.x_southbrook_material_species),
            ]
            if task.x_southbrook_unit_count:
                pieces.append(_("%s units") % task.x_southbrook_unit_count)
            if task.x_southbrook_hardware_specs:
                pieces.append(task.x_southbrook_hardware_specs)
            task.x_southbrook_cabinet_spec_summary = " | ".join(
                piece for piece in pieces if piece
            )

    def _southbrook_collect_readiness_gates(self):
        gates = super()._southbrook_collect_readiness_gates()
        self.ensure_one()
        for item in self.sudo().x_southbrook_checklist_item_ids:
            if item.done or item.waived:
                continue
            state = "blocked" if item.required else "warning"
            current = gates.get(item.gate) or {}
            if current.get("state") == "blocked" and state != "blocked":
                continue
            message = (
                _("A required release checklist item is incomplete.")
                if item.required else
                _("An optional release checklist item needs review.")
            )
            gates[item.gate] = self._southbrook_default_gate(
                item.gate,
                state=state,
                message=message,
                action=_("Open the Release Checklist and clear the %s gate item.")
                % dict(GATE_SELECTION).get(item.gate, item.gate),
                blocking=item.required,
            )
            if item.required:
                break
        if self.x_southbrook_install_due_date and not self.date_deadline:
            current = gates.get("install") or {}
            if current.get("state") != "blocked":
                gates["install"] = self._southbrook_default_gate(
                    "install",
                    state="warning",
                    message=_("Install due date is set but Project deadline is blank."),
                    action=_("Set the Project deadline or confirm the install package."),
                )
        return gates

    def action_southbrook_open_family_progress(self):
        self.ensure_one()
        Family = self.env["southbrook.cabinet.family"]
        family = Family.search([
            ("code", "=", self.x_southbrook_cabinet_family),
        ], limit=1)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Cabinet Family Progress"),
            "res_model": "southbrook.cabinet.family",
            "view_mode": "kanban,list,form",
        }
        if family:
            action.update({
                "view_mode": "form",
                "res_id": family.id,
            })
        else:
            action["domain"] = [("code", "=", self.x_southbrook_cabinet_family)]
        return action
