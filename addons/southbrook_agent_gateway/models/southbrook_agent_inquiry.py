# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.agent.inquiry — one record per AI-agent quote request.

The inquiry is the audit trail + verification state machine sitting
between the public API and the CRM records it creates:

    agent POST /quote-request
        └─> inquiry (state=new)  + res.partner  + crm.lead
                └─> verification email to the human customer
                        └─> customer clicks /agent/verify/<token>
                                └─> inquiry state=verified, lead gets a
                                    logged note so sales knows the
                                    contact info is confirmed real.

All record creation happens in `submit()` (called sudo from the public
controller) so the whole flow is unit-testable without HTTP, mirroring
how southbrook.qr.part keeps parse/serialize out of its controller.

Contact-info validation lives here too:
  * email  — odoo.tools.email_normalize (reject on failure)
  * phone  — phone_validation E.164 formatting (reject on failure;
             optional field, absent is fine)
  * names/description — length caps + control-char strip
"""
import logging
import re
import secrets

from odoo import _, api, fields, models
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)

_MAX_NAME = 120
_MAX_EMAIL = 254
_MAX_PHONE = 40
_MAX_TEXT = 4000
_MAX_SHORT = 200

# Strip ASCII control chars (keep \n in long text).
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value, max_len, keep_newlines=False):
    """Coerce to a trimmed, control-char-free, length-capped string."""
    if not isinstance(value, str):
        return ""
    value = _CTRL_RE.sub("", value)
    if not keep_newlines:
        value = value.replace("\n", " ").replace("\r", " ")
    return value.strip()[:max_len]


class SouthbrookAgentInquiry(models.Model):
    _name = "southbrook.agent.inquiry"
    _description = "AI Agent Quote Inquiry"
    _order = "create_date desc"
    _rec_name = "reference"

    reference = fields.Char(
        required=True, readonly=True, copy=False, index=True,
        default=lambda self: self.env["ir.sequence"].sudo().next_by_code(
            "southbrook.agent.inquiry") or "AIQ-NEW")
    state = fields.Selection(
        [("new", "Awaiting Email Verification"),
         ("verified", "Email Verified"),
         ("spam", "Spam / Discarded")],
        default="new", required=True, index=True)

    # Who the AI agent said it was. Free-text, informational only —
    # never trusted for anything security-relevant.
    agent_name = fields.Char(readonly=True)
    agent_platform = fields.Char(readonly=True)
    agent_user_agent = fields.Char(readonly=True)

    customer_name = fields.Char(readonly=True)
    email = fields.Char(readonly=True, index=True)
    phone = fields.Char(readonly=True)
    project_description = fields.Text(readonly=True)
    room_type = fields.Char(readonly=True)
    budget_range = fields.Char(readonly=True)
    timeline = fields.Char(readonly=True)

    partner_id = fields.Many2one("res.partner", readonly=True, ondelete="set null")
    lead_id = fields.Many2one("crm.lead", readonly=True, ondelete="set null")

    # verify_token goes into the customer's email link (proves inbox
    # control). status_token is returned once to the submitting agent so
    # it can poll status without being able to enumerate other people's
    # inquiries by reference.
    verify_token = fields.Char(readonly=True, copy=False, index=True)
    status_token = fields.Char(readonly=True, copy=False)
    verified_at = fields.Datetime(readonly=True)

    _reference_uniq = models.Constraint(
        "UNIQUE(reference)", "Inquiry reference must be unique.")
    _verify_token_uniq = models.Constraint(
        "UNIQUE(verify_token)", "Verify token must be unique.")

    # ------------------------------------------------------------------
    # Validation helpers (pure; no ORM) — exposed for the controller's
    # early-reject path and reused by submit().
    # ------------------------------------------------------------------
    @api.model
    def validate_payload(self, payload):
        """Return (cleaned_dict, None) or (None, error_detail_str)."""
        if not isinstance(payload, dict):
            return None, "Request body must be a JSON object."
        customer = payload.get("customer")
        project = payload.get("project")
        agent = payload.get("agent") or {}
        if not isinstance(customer, dict):
            return None, "customer must be an object with name and email."
        if not isinstance(project, dict):
            return None, "project must be an object with a description."
        if not isinstance(agent, dict):
            return None, "agent, when provided, must be an object."

        if payload.get("consent") is not True:
            return None, (
                "consent must be true — the customer must have agreed to "
                "share their contact information with Southbrook Cabinetry.")

        name = _clean(customer.get("name"), _MAX_NAME)
        if len(name) < 2:
            return None, "customer.name is required (2+ characters)."

        raw_email = _clean(customer.get("email"), _MAX_EMAIL)
        email = email_normalize(raw_email)
        if not email:
            return None, "customer.email is not a valid email address."

        phone = _clean(customer.get("phone"), _MAX_PHONE)
        if phone:
            formatted = self._format_phone(phone)
            if not formatted:
                return None, (
                    "customer.phone could not be validated — provide an "
                    "E.164 or full national number, or omit it.")
            phone = formatted

        description = _clean(
            project.get("description"), _MAX_TEXT, keep_newlines=True)
        if len(description) < 10:
            return None, (
                "project.description is required (10+ characters) — what "
                "does the customer want built?")

        return {
            "customer_name": name,
            "email": email,
            "phone": phone,
            "project_description": description,
            "room_type": _clean(project.get("room_type"), _MAX_SHORT),
            "budget_range": _clean(project.get("budget_range"), _MAX_SHORT),
            "timeline": _clean(project.get("timeline"), _MAX_SHORT),
            "agent_name": _clean(agent.get("name"), _MAX_SHORT),
            "agent_platform": _clean(agent.get("platform"), _MAX_SHORT),
        }, None

    @api.model
    def _format_phone(self, phone):
        """E.164-format `phone` against the company country. Returns the
        formatted number or False. Never raises."""
        try:
            from odoo.addons.phone_validation.tools import phone_validation
            country = self.env.company.country_id
            return phone_validation.phone_format(
                phone,
                country.code if country else "CA",
                country.phone_code if country else 1,
                force_format="E164",
                raise_exception=False,
            ) or False
        except Exception:  # noqa: BLE001 — validation must never 500
            return False

    # ------------------------------------------------------------------
    # Submission — the whole partner + lead + email side-effect chain.
    # ------------------------------------------------------------------
    @api.model
    def submit(self, cleaned, user_agent="", is_spam=False):
        """Create the inquiry (+ partner + lead + verification email
        unless spam). Returns the inquiry record. Caller is the public
        controller running sudo; `cleaned` is validate_payload() output.
        """
        vals = dict(
            cleaned,
            agent_user_agent=_clean(user_agent, _MAX_SHORT),
            verify_token=secrets.token_urlsafe(32),
            status_token=secrets.token_urlsafe(24),
        )
        if is_spam:
            # Honeypot hit: keep the audit record, create nothing else,
            # respond upstream exactly like a success so the bot learns
            # nothing.
            vals["state"] = "spam"
            return self.create(vals)

        partner = self._find_or_create_partner(cleaned)
        lead = self._create_lead(cleaned, partner)
        inquiry = self.create(dict(
            vals, partner_id=partner.id, lead_id=lead.id))
        inquiry._send_verification_email()
        return inquiry

    def _find_or_create_partner(self, cleaned):
        Partner = self.env["res.partner"]
        partner = Partner.search(
            [("email_normalized", "=", cleaned["email"])], limit=1)
        if partner:
            # Existing contact: never overwrite their name/phone from an
            # unverified third-party submission — just backfill blanks.
            updates = {}
            if not partner.phone and cleaned["phone"]:
                updates["phone"] = cleaned["phone"]
            if updates:
                partner.write(updates)
            return partner
        tag = self.env.ref(
            "southbrook_agent_gateway.partner_category_ai_agent_lead",
            raise_if_not_found=False)
        return Partner.create({
            "name": cleaned["customer_name"],
            "email": cleaned["email"],
            "phone": cleaned["phone"] or False,
            "category_id": [(6, 0, tag.ids)] if tag else False,
            "comment": _(
                "Created from an AI-agent quote request "
                "(southbrook_agent_gateway). Contact info pending email "
                "verification."),
        })

    def _create_lead(self, cleaned, partner):
        source = self.env.ref(
            "southbrook_agent_gateway.utm_source_ai_agent",
            raise_if_not_found=False)
        medium = self.env.ref(
            "southbrook_agent_gateway.utm_medium_agent_api",
            raise_if_not_found=False)
        details = [
            _("Quote request submitted by an AI agent on the customer's "
              "behalf."),
            "",
            _("Project: %s") % cleaned["project_description"],
        ]
        for label, key in (
            (_("Room type"), "room_type"),
            (_("Budget range"), "budget_range"),
            (_("Timeline"), "timeline"),
            (_("Agent"), "agent_name"),
            (_("Agent platform"), "agent_platform"),
        ):
            if cleaned.get(key):
                details.append("%s: %s" % (label, cleaned[key]))
        details.append("")
        details.append(_(
            "Contact info is UNVERIFIED until the customer clicks the "
            "verification email."))
        return self.env["crm.lead"].create({
            "name": _("AI-agent quote request — %s") % cleaned["customer_name"],
            "type": "lead",
            "partner_id": partner.id,
            "contact_name": cleaned["customer_name"],
            "email_from": cleaned["email"],
            "phone": cleaned["phone"] or False,
            "description": "\n".join(details),
            "source_id": source.id if source else False,
            "medium_id": medium.id if medium else False,
        })

    def _send_verification_email(self):
        self.ensure_one()
        template = self.env.ref(
            "southbrook_agent_gateway.mail_template_verify_inquiry",
            raise_if_not_found=False)
        if not template:
            _logger.warning(
                "southbrook_agent_gateway: verification mail template "
                "missing; inquiry %s stays unverified until manual "
                "follow-up.", self.reference)
            return
        try:
            template.sudo().send_mail(self.id)
        except Exception as exc:  # noqa: BLE001 — a mail failure must
            # never fail the API request; the lead exists either way and
            # sales can verify by phone.
            _logger.warning(
                "southbrook_agent_gateway: verification mail send failed "
                "for %s: %s", self.reference, exc)

    # ------------------------------------------------------------------
    # Verification + status
    # ------------------------------------------------------------------
    @api.model
    def verify_by_token(self, token):
        """Flip the inquiry to verified. Returns the inquiry or empty
        recordset. Idempotent: re-clicking the link is a no-op success."""
        if not token or not isinstance(token, str) or len(token) > 128:
            return self.browse()
        inquiry = self.search([("verify_token", "=", token)], limit=1)
        if not inquiry or inquiry.state == "spam":
            return self.browse()
        if inquiry.state != "verified":
            inquiry.write({
                "state": "verified",
                "verified_at": fields.Datetime.now(),
            })
            if inquiry.lead_id:
                inquiry.lead_id.message_post(body=_(
                    "Customer verified their email address via the "
                    "AI-agent gateway confirmation link (%s).",
                    inquiry.reference))
        return inquiry

    def status_payload(self):
        self.ensure_one()
        stage = self.lead_id.stage_id.name if self.lead_id else None
        return {
            "reference": self.reference,
            "state": self.state,
            "email_verified": self.state == "verified",
            "sales_stage": stage,
            "assigned": bool(self.lead_id and self.lead_id.user_id),
        }
