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
        # Sales prospect discovered by the external Hermes Console
        # lead_prospector agent loop (Gemini-grounded Google search).
        # On apply, creates a crm.lead record from the payload —
        # company / city / source_url / why_fit / contact_hint.
        ("prospect", "Sales Prospect"),
    ], default="task", required=True, tracking=True)
    priority = fields.Selection([
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("blocker", "Blocker"),
    ], default="normal", required=True, tracking=True)
    agent_partner_id = fields.Many2one(
        "res.partner",
        default=lambda self: self._default_agent_partner_id(),
        readonly=True,
        copy=False,
    )
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
    # Set when a recommendation_type='prospect' recommendation is applied —
    # the freshly-created crm.lead record. Stays NULL for non-prospect
    # recommendation types.
    created_crm_lead_id = fields.Many2one(
        "crm.lead", readonly=True, copy=False,
    )

    @api.model
    def _default_agent_partner_id(self):
        return self.env.ref(
            "southbrook_hermes.partner_fabio_agent",
            raise_if_not_found=False,
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
            elif rec.recommendation_type == "prospect":
                lead = rec._create_crm_lead()
                values["created_crm_lead_id"] = lead.id
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

    def _create_crm_lead(self):
        """Create a crm.lead from a recommendation_type='prospect' payload.

        Payload contract (set by the hermes-console lead_prospector loop):

            {
                "company":       str,   # business name
                "lead_type":     str,   # construction_renovation_project / kitchen_manufacturer / ...
                "city":          str,   # "Toronto, ON"
                "source_url":    str,   # citable URL Gemini surfaced
                "contact_hint":  str,   # email / phone / form URL (optional)
                "why_fit":       str,   # 1-2 sentence rationale
                ...
            }

        Mapping:
          * partner_name = company (the lead's company name on crm.lead)
          * name         = title — Odoo's crm.lead.name is the opportunity title
          * city         = first token of payload.city (everything before the comma)
          * description  = why_fit + proposed_action + source_url + contact_hint
                           (a single human-readable block for the salesperson)
          * website      = source_url IF it looks like a real domain
          * tag_ids      = synthesise a tag for the lead_type so sales can
                           filter the pipeline by where Hermes found them
          * priority     = map from recommendation.priority (high/normal/low/blocker)
          * referred     = 'Hermes Lead Prospector' (free-text attribution)
        """
        self.ensure_one()
        payload = self._payload()

        company = (payload.get("company") or "").strip() or _("Unknown company")
        city_raw = (payload.get("city") or "").strip()
        # "Toronto, ON" → city="Toronto"; we leave the province in the
        # description rather than guessing a state_id m2o lookup.
        city = city_raw.split(",")[0].strip() if city_raw else ""

        why_fit = (payload.get("why_fit") or "").strip()
        source_url = (payload.get("source_url") or "").strip()
        contact_hint = (payload.get("contact_hint") or "").strip()
        lead_type = (payload.get("lead_type") or "").strip()

        # Build the description block — sales rep gets one self-contained read.
        desc_parts = []
        if why_fit:
            desc_parts.append(_("Why this prospect fits Southbrook:"))
            desc_parts.append(why_fit)
        if self.proposed_action:
            desc_parts.append("")
            desc_parts.append(_("Proposed next step: %s") % self.proposed_action)
        if source_url:
            desc_parts.append("")
            desc_parts.append(_("Source: %s") % source_url)
        if contact_hint:
            desc_parts.append(_("Contact hint: %s") % contact_hint)
        if lead_type:
            desc_parts.append(_("Lead type: %s") % lead_type)
        description = "\n".join(desc_parts) if desc_parts else self.summary

        priority_map = {
            "low": "0",
            "normal": "1",
            "high": "2",
            "blocker": "3",
        }
        lead_vals = {
            "name": self.name,
            "partner_name": company,
            "city": city,
            "description": description,
            "priority": priority_map.get(self.priority, "1"),
            "referred": _("Hermes Lead Prospector"),
            "type": "lead",
        }
        # Set website if source_url looks like a real domain (filter out
        # Google's grounding redirector which carries no salespable value).
        if source_url and "vertexaisearch.cloud.google.com" not in source_url:
            lead_vals["website"] = source_url

        # Synthesise a crm.tag for the lead_type so the sales pipeline can
        # filter "all Hermes-found construction projects" with one click.
        if lead_type:
            tag = self.env["crm.tag"].search(
                [("name", "=", _("Hermes: %s") % lead_type)], limit=1,
            )
            if not tag:
                tag = self.env["crm.tag"].create(
                    {"name": _("Hermes: %s") % lead_type}
                )
            lead_vals["tag_ids"] = [(4, tag.id)]

        lead = self.env["crm.lead"].create(lead_vals)
        lead.message_post(
            body=_(
                "Created from Fabio prospect recommendation %s "
                "(Hermes Lead Prospector — Gemini-grounded discovery)."
            ) % self.display_name,
        )
        return lead
