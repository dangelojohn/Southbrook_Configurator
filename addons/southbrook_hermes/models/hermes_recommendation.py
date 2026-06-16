# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SouthbrookHermesRecommendation(models.Model):
    _name = "southbrook.hermes.recommendation"
    _description = "HERMES Recommendation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, tracking=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("ready", "Ready"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("applied", "Applied"),
    ], default="draft", required=True, tracking=True)
    recommendation_type = fields.Selection([
        ("task", "Task"),
        ("risk", "Risk"),
        ("note", "Note"),
        ("followup", "Follow-up"),
    ], default="task", required=True, tracking=True)
    priority = fields.Selection([
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("blocker", "Blocker"),
    ], default="normal", required=True, tracking=True)
    summary = fields.Text(required=True)
    rationale = fields.Text()
    proposed_action = fields.Text()
    source_model = fields.Char()
    source_res_id = fields.Integer()
    payload_json = fields.Text(default="{}", required=True)
    agent_run_id = fields.Char(index=True)
    model_provider = fields.Char()
    model_name = fields.Char()
    reviewer_id = fields.Many2one(
        "res.users", readonly=True, copy=False, tracking=True,
    )
    reviewed_date = fields.Datetime(readonly=True, copy=False)
    applied_date = fields.Datetime(readonly=True, copy=False)
    created_task_id = fields.Many2one(
        "project.task", readonly=True, copy=False,
    )

    @api.constrains("payload_json")
    def _check_payload_json(self):
        for rec in self:
            payload = rec._payload()
            if not isinstance(payload, dict):
                raise ValidationError(_("Payload JSON must be a JSON object."))

    def _payload(self):
        self.ensure_one()
        try:
            return json.loads(self.payload_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValidationError(_("Payload JSON is invalid: %s") % exc) from exc

    def action_mark_ready(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft recommendations can be marked ready."))
            rec.state = "ready"
        return True

    def action_approve(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state not in ("draft", "ready"):
                raise UserError(_("Only draft or ready recommendations can be approved."))
            rec.write({
                "state": "approved",
                "reviewer_id": self.env.user.id,
                "reviewed_date": now,
            })
            rec.message_post(body=_("Fabio recommendation approved."))
        return True

    def action_reject(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state == "applied":
                raise UserError(_("Applied recommendations cannot be rejected."))
            rec.write({
                "state": "rejected",
                "reviewer_id": self.env.user.id,
                "reviewed_date": now,
            })
            rec.message_post(body=_("Fabio recommendation rejected."))
        return True

    def action_apply(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != "approved":
                raise UserError(_("A recommendation must be approved before it can be applied."))
            values = {"state": "applied", "applied_date": now}
            if rec.recommendation_type == "task":
                task = rec._create_project_task()
                values["created_task_id"] = task.id
            rec.write(values)
            rec.message_post(body=_("Fabio recommendation applied."))
        return True

    def _create_project_task(self):
        self.ensure_one()
        payload = self._payload()
        project_id = payload.get("project_id")
        if not project_id:
            raise UserError(_("Task recommendations require payload.project_id."))
        project = self.env["project.project"].browse(project_id).exists()
        if not project:
            raise UserError(_("Task recommendation project does not exist."))

        task_name = payload.get("task_name") or self.name
        task = self.env["project.task"].create({
            "project_id": project.id,
            "name": task_name,
            "description": self._task_description(payload),
        })
        task.message_post(
            body=_("Created from Fabio recommendation %s.") % self.display_name,
        )
        return task

    def _task_description(self, payload):
        self.ensure_one()
        if payload.get("description"):
            return payload["description"]
        parts = [self.summary]
        if self.proposed_action:
            parts.append(_("Proposed action: %s") % self.proposed_action)
        if self.rationale:
            parts.append(_("Rationale: %s") % self.rationale)
        return "\n\n".join(parts)
