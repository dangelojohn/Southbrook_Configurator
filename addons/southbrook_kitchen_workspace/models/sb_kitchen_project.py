# SPDX-License-Identifier: LGPL-3.0-only
"""sb.kitchen.project — the parent record for a kitchen design engagement."""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


PROJECT_STATES = [
    ("draft", "Draft"),
    ("designing", "Designing"),
    ("awaiting_customer", "Awaiting Customer"),
    ("approved", "Customer Approved"),
    ("in_production", "In Production"),
    ("done", "Done"),
    ("cancelled", "Cancelled"),
]

# Aligns with the configurator's four series (in-repo CLAUDE.md §2).
THEME_CHOICES = [
    ("signature", "Signature"),
    ("elegance", "Elegance"),
    ("contemporary", "Contemporary"),
    ("contractor", "Contractor"),
]

# Valid state transitions — each tuple is (from, to). Off-graph
# transitions raise UserError so a renderer/automation can't yank a
# project into 'approved' without going through awaiting_customer.
VALID_TRANSITIONS = {
    ("draft", "designing"),
    ("draft", "cancelled"),
    ("designing", "awaiting_customer"),
    ("designing", "cancelled"),
    ("awaiting_customer", "approved"),
    ("awaiting_customer", "designing"),
    ("awaiting_customer", "cancelled"),
    ("approved", "in_production"),
    ("approved", "cancelled"),
    ("in_production", "done"),
    ("in_production", "cancelled"),
}


class SbKitchenProject(models.Model):
    _name = "sb.kitchen.project"
    _description = "Southbrook Kitchen Project"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_created desc, id desc"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        readonly=True, copy=False, default=lambda self: _("New"),
        help="Sequential project code (KP/2026/000123).",
    )
    state = fields.Selection(
        PROJECT_STATES, default="draft", tracking=True, required=True,
        index=True,
    )
    theme = fields.Selection(THEME_CHOICES, tracking=True)
    date_created = fields.Date(
        default=fields.Date.context_today, readonly=True, copy=False,
    )
    date_target = fields.Date(string="Target Completion")
    date_completed = fields.Date(readonly=True, copy=False)

    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, tracking=True,
    )
    opportunity_id = fields.Many2one("crm.lead", string="CRM Opportunity")
    salesperson_id = fields.Many2one(
        "res.users", string="Designer / Salesperson",
        default=lambda self: self.env.user, index=True,
    )

    # Child collections.
    design_option_ids = fields.One2many(
        "sb.kitchen.design.option", "project_id", string="Design Options",
    )
    selected_design_option_id = fields.Many2one(
        "sb.kitchen.design.option", string="Selected Option",
        compute="_compute_selected_design_option", store=True,
    )
    ai_analysis_id = fields.Many2one(
        "sb.kitchen.ai.analysis", string="AI Room Analysis",
    )
    appliance_ids = fields.One2many(
        "sb.kitchen.appliance", "project_id", string="Appliances",
    )
    approval_ids = fields.One2many(
        "sb.kitchen.approval", "project_id", string="Approvals",
    )

    # Outbound links.
    sale_order_id = fields.Many2one("sale.order", string="Quote / Sale Order")

    # Room bridge — Phase A. A project draws its floor plan from the
    # first room of its sale_order. The room is created lazily by
    # action_open_room_layout when the designer first asks for the plan.
    room_id = fields.Many2one(
        "southbrook.room",
        compute="_compute_room_id", store=False,
        string="Active Room",
    )
    room_count = fields.Integer(compute="_compute_room_id", store=False)

    notes = fields.Html()

    @api.depends("design_option_ids.is_selected")
    def _compute_selected_design_option(self):
        for project in self:
            selected = project.design_option_ids.filtered("is_selected")
            project.selected_design_option_id = selected[:1]

    @api.depends("sale_order_id.room_ids")
    def _compute_room_id(self):
        for project in self:
            rooms = project.sale_order_id.room_ids if project.sale_order_id else False
            project.room_id = rooms[:1] if rooms else False
            project.room_count = len(rooms) if rooms else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", _("New")) == _("New"):
                vals["code"] = self.env["ir.sequence"].next_by_code(
                    "sb.kitchen.project"
                ) or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def action_set_state(self, new_state: str):
        """Move the project to new_state if the transition is valid."""
        for project in self:
            current = project.state
            if (current, new_state) not in VALID_TRANSITIONS:
                raise UserError(_(
                    "Invalid state transition: %(from)s → %(to)s. "
                    "Valid transitions from %(from)s are: %(valid)s."
                ) % {
                    "from": current,
                    "to": new_state,
                    "valid": ", ".join(t for (f, t) in VALID_TRANSITIONS
                                       if f == current) or "(none)",
                })
            vals = {"state": new_state}
            if new_state == "done":
                vals["date_completed"] = fields.Date.context_today(project)
            project.write(vals)

    # Convenience action buttons (one per next-step the designer cares about).
    def action_start_designing(self):
        self.action_set_state("designing")

    def action_submit_to_customer(self):
        self._require_at_least_one_design_option()
        self.action_set_state("awaiting_customer")
        self._send_lifecycle_email("email_template_concepts_ready")

    def action_customer_approves(self):
        self._require_selected_design_option()
        self.action_set_state("approved")
        self._send_lifecycle_email("email_template_design_approved")

    def action_release_to_production(self):
        self.action_set_state("in_production")
        self._send_lifecycle_email("email_template_released_to_production")

    def action_done(self):
        self.action_set_state("done")
        self._send_lifecycle_email("email_template_project_done")

    def action_cancel(self):
        # Intentional: cancellation goes out-of-band (chatter + operator
        # phone call). An automated cancellation email reads as cold for
        # what is usually a delicate conversation.
        self.action_set_state("cancelled")

    def _require_at_least_one_design_option(self):
        for project in self:
            if not project.design_option_ids:
                raise UserError(_(
                    "Cannot submit to customer: project has no design "
                    "options. Create at least one in the Design Options tab."
                ))

    def _require_selected_design_option(self):
        for project in self:
            if not project.selected_design_option_id:
                raise UserError(_(
                    "Cannot record customer approval: no design option "
                    "is selected. Mark exactly one as selected first."
                ))

    # ------------------------------------------------------------------
    # Lifecycle email
    # ------------------------------------------------------------------
    def _send_lifecycle_email(self, template_xml_id: str):
        """Send a lifecycle mail.template to the audience that template names.

        Templates are seeded in data/mail_templates.xml. Failure to find
        a template (e.g. template_xml_id misspelled) is a warning, not a
        block — the state machine ran first and is the authoritative
        contract; email is a side-effect.
        """
        full_xml_id = f"southbrook_kitchen_workspace.{template_xml_id}"
        template = self.env.ref(full_xml_id, raise_if_not_found=False)
        if not template:
            return  # template removed / renamed — caller carries on
        # Render/queue as sudo so a non-privileged designer can send the
        # template (its access is otherwise restricted); the body renders only
        # this project's own fields via auto-escaped t-out — no injection.
        template = template.sudo()
        for project in self:
            try:
                template.with_context(
                    lang=project.partner_id.lang or self.env.user.lang,
                ).send_mail(project.id, force_send=False)
            except Exception:
                # The transition must not roll back on email failure.
                _logger.warning(
                    "Lifecycle email %s failed for project %s",
                    full_xml_id, project.code, exc_info=True,
                )

    # ------------------------------------------------------------------
    # AI-analysis confirmation gate (init-doc GAP-02 / Module 6)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Room Layout bridge
    # ------------------------------------------------------------------
    def action_open_room_layout(self):
        """Open the Order Builder's Room Layout tab for this project's
        room. Lazily provisions a draft sale.order + a default kitchen
        room if either is missing — the designer never has to
        pre-create those by hand.
        """
        self.ensure_one()
        # 1. Ensure sale.order
        order = self.sale_order_id
        if not order:
            order = self.env["sale.order"].create({
                "partner_id": self.partner_id.id,
                "origin": self.code or self.name,
            })
            self.sale_order_id = order
        # 2. Ensure at least one room
        room = order.room_ids[:1]
        if not room:
            room = self.env["southbrook.room"].create({
                "name": self.name or "Main Kitchen",
                "order_id": order.id,
                "room_type": "kitchen",
            })
        # 3. Open the Order Builder form scrolled to Room Layout
        return {
            "type": "ir.actions.act_window",
            "name": "Room Layout",
            "res_model": "sale.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
            "context": {"default_sb_active_tab": "room_layout"},
        }

    def is_ready_for_config_engine(self) -> bool:
        """The configuration engine MUST refuse to run unless every
        dimensional input is human-confirmed. Returns True only when the
        AI analysis exists, is confirmed, and every appliance is
        confirmed."""
        self.ensure_one()
        if not self.ai_analysis_id or not self.ai_analysis_id.confirmed_by_human:
            return False
        if any(not a.confirmed_by_human for a in self.appliance_ids):
            return False
        return True
