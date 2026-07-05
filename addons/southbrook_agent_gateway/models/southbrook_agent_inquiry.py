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
import hmac
import logging
import re
import secrets

from odoo import _, api, fields, models
from odoo.tools import email_normalize, plaintext2html

_logger = logging.getLogger(__name__)

_MAX_NAME = 120
_MAX_EMAIL = 254
_MAX_PHONE = 40
_MAX_TEXT = 4000
_MAX_SHORT = 200

# v2 draft-quote line-item bounds. A real kitchen is dozens of cabinets,
# not thousands — cap both the line count and per-line qty to keep the
# create loop bounded and the blast radius of scripted abuse small.
_MAX_LINE_ITEMS = 60
_MAX_LINE_QTY = 99

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
    # Address (v2, all optional) — captured for service-area triage +
    # the eventual quotation ship/invoice address. Stored raw on the
    # inquiry as an audit snapshot; also written onto the partner.
    street = fields.Char(readonly=True)
    city = fields.Char(readonly=True)
    state_name = fields.Char(readonly=True)
    zip_code = fields.Char(readonly=True)
    country_name = fields.Char(readonly=True)
    project_description = fields.Text(readonly=True)
    room_type = fields.Char(readonly=True)
    budget_range = fields.Char(readonly=True)
    timeline = fields.Char(readonly=True)

    partner_id = fields.Many2one("res.partner", readonly=True, ondelete="set null")
    lead_id = fields.Many2one("crm.lead", readonly=True, ondelete="set null")
    # v2 — the draft quotation created when the agent submitted cabinet
    # selections (absent for lead-only /quote-request submissions).
    sale_order_id = fields.Many2one(
        "sale.order", readonly=True, ondelete="set null")

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

        # Address (v2) — optional; a dict when present.
        address = payload.get("address") or {}
        if not isinstance(address, dict):
            return None, "address, when provided, must be an object."

        return {
            "customer_name": name,
            "email": email,
            "phone": phone,
            "street": _clean(address.get("street"), _MAX_SHORT),
            "city": _clean(address.get("city"), _MAX_SHORT),
            "state_name": _clean(
                address.get("state") or address.get("province"), _MAX_SHORT),
            "zip_code": _clean(
                address.get("zip") or address.get("postal_code"), 20),
            "country_name": _clean(address.get("country"), _MAX_SHORT),
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
        formatted number or False on ANY failure — including the case
        phone_validation can't parse a real number out of the input at
        all (it returns the input unchanged rather than raising when
        force_format can't apply). We reject a result that still contains
        letters or didn't come back in +E.164 shape, so free text like
        'call me maybe' can't slip through into the CRM as a phone."""
        try:
            from odoo.addons.phone_validation.tools import phone_validation
            country = self.env.company.country_id
            formatted = phone_validation.phone_format(
                phone,
                country.code if country else "CA",
                country.phone_code if country else 1,
                force_format="E164",
                raise_exception=False,
            )
        except Exception:  # noqa: BLE001 — validation must never 500
            return False
        if not formatted or not isinstance(formatted, str):
            return False
        # A valid E.164 result is "+" followed by digits only. Anything
        # with a letter or without the leading "+" means the library
        # echoed unparseable input back — treat as invalid.
        if not formatted.startswith("+") or not formatted[1:].isdigit():
            return False
        return formatted

    # ------------------------------------------------------------------
    # Line-item validation for v2 draft quotes. Resolves customer-
    # supplied SKUs against the PUBLIC cabinet catalog only (templates
    # carrying southbrook_category) — an agent can never reference an
    # arbitrary product.template id, only a real published cabinet SKU.
    # ------------------------------------------------------------------
    @api.model
    def validate_line_items(self, raw_items):
        """Return (list_of_{template, qty}, None) or (None, error). An
        empty/absent list returns ([], None) — lead-only, no order."""
        if raw_items in (None, ""):
            return [], None
        if not isinstance(raw_items, list):
            return None, "line_items must be a list of {sku, qty} objects."
        if not raw_items:
            return [], None
        if len(raw_items) > _MAX_LINE_ITEMS:
            return None, ("line_items has too many entries (max %d)."
                          % _MAX_LINE_ITEMS)

        Template = self.env["product.template"].sudo()
        resolved = []
        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                return None, "line_items[%d] must be an object." % idx
            sku = _clean(item.get("sku"), 64)
            if not sku:
                return None, "line_items[%d] is missing sku." % idx
            try:
                qty = int(item.get("qty") or 1)
            except (TypeError, ValueError):
                return None, "line_items[%d].qty must be an integer." % idx
            if qty < 1 or qty > _MAX_LINE_QTY:
                return None, ("line_items[%d].qty must be between 1 and %d."
                              % (idx, _MAX_LINE_QTY))
            tmpl = Template.search([
                ("default_code", "=", sku),
                ("southbrook_category", "!=", False),
                ("active", "=", True),
            ], limit=1)
            if not tmpl:
                return None, ("line_items[%d]: unknown SKU %r — use a SKU "
                              "from /agent/api/v1/offerings." % (idx, sku))
            resolved.append({"template": tmpl, "qty": qty})
        return resolved, None

    # ------------------------------------------------------------------
    # Submission — the whole partner + lead + email side-effect chain.
    # ------------------------------------------------------------------
    @api.model
    def submit(self, cleaned, user_agent="", is_spam=False, line_items=None):
        """Create the inquiry (+ partner + lead + optional draft quote +
        verification email unless spam). Returns the inquiry record.
        Caller is the public controller running sudo; `cleaned` is
        validate_payload() output; `line_items` is validate_line_items()
        output (a list of {template, qty}; empty => lead-only, no order).
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

        partner, is_new_partner = self._find_or_create_partner(cleaned)
        lead = self._create_lead(cleaned, partner, is_new_partner)
        order = False
        if line_items:
            order = self._create_draft_order(cleaned, partner, line_items)
            if order and lead:
                lead.description = (lead.description or "") + "\n\n" + _(
                    "Self-service draft quotation %s created by the agent "
                    "(%d line(s)). Awaiting sales review.") % (
                        order.name, len(order.order_line))
        inquiry = self.create(dict(
            vals,
            partner_id=partner.id,
            lead_id=lead.id,
            sale_order_id=order.id if order else False,
        ))
        inquiry._send_verification_email()
        return inquiry

    def _find_or_create_partner(self, cleaned):
        """Return (partner, is_new). is_new drives whether downstream
        records (the lead) may carry contact fields that Odoo syncs back
        onto the partner — see _create_lead."""
        Partner = self.env["res.partner"]
        partner = Partner.search(
            [("email_normalized", "=", cleaned["email"])], limit=1)
        if partner:
            # SECURITY: an EXISTING contact was matched only by email —
            # which an attacker who merely KNOWS a customer's address
            # could supply. Never write ANY field (name, phone, address)
            # onto a pre-existing partner from an unverified third-party
            # submission; doing so would let a stranger plant a phone
            # number / address on a real customer's record. NOTE: this
            # includes the INDIRECT write Odoo performs when a crm.lead
            # linked to this partner carries phone/street — _create_lead
            # withholds those fields for a reused partner (is_new=False).
            # The inquiry keeps the submitted values as an audit snapshot;
            # a rep reconciles them after the person-to-person follow-up.
            return partner, False
        tag = self.env.ref(
            "southbrook_agent_gateway.partner_category_ai_agent_lead",
            raise_if_not_found=False)
        agent_label = cleaned.get("agent_name") or _("an AI agent")
        return Partner.create(dict(
            {
                "name": cleaned["customer_name"],
                "email": cleaned["email"],
                "phone": cleaned["phone"] or False,
                # "AI Agent Lead" tag (res.partner.category) flags this
                # contact as AI-agent-originated in every partner view.
                "category_id": [(6, 0, tag.ids)] if tag else False,
                "comment": _(
                    "⚠ Contact created automatically by %s via the "
                    "Southbrook AI-agent gateway — NOT entered by a "
                    "person. Contact info is pending customer email "
                    "verification; confirm on the person-to-person "
                    "follow-up before relying on it.") % agent_label,
            },
            **self._partner_address_vals(cleaned),
        ))

    def _partner_address_vals(self, cleaned):
        """Best-effort address fields for a NEW partner. Country/state
        are resolved leniently (skipped, never rejected, if unmatched) so
        an unrecognised country name can't fail the whole submission."""
        vals = {}
        if cleaned.get("street"):
            vals["street"] = cleaned["street"]
        if cleaned.get("city"):
            vals["city"] = cleaned["city"]
        if cleaned.get("zip_code"):
            vals["zip"] = cleaned["zip_code"]
        country = self.browse()
        if cleaned.get("country_name"):
            Country = self.env["res.country"]
            name = cleaned["country_name"]
            country = (Country.search([("code", "=ilike", name)], limit=1)
                       if len(name) == 2 else self.browse())
            if not country:
                country = Country.search([("name", "=ilike", name)], limit=1)
            if country:
                vals["country_id"] = country.id
        if cleaned.get("state_name"):
            State = self.env["res.country.state"]
            domain = [("name", "=ilike", cleaned["state_name"])]
            if country:
                domain.append(("country_id", "=", country.id))
            state = State.search(domain, limit=1)
            if not state:
                state = State.search(
                    [("code", "=ilike", cleaned["state_name"])]
                    + ([("country_id", "=", country.id)] if country else []),
                    limit=1)
            if state:
                vals["state_id"] = state.id
        return vals

    # ------------------------------------------------------------------
    # v2 — self-service draft quotation. Creates a real sale.order in the
    # SAME shape the customer Order Builder produces (draft/base variant
    # per template, then flipped to 'sent' = Submitted for Review), so it
    # lands in the identical sales-review queue a human-built quote does.
    # NEVER confirmed (that would spawn Manufacturing Orders) — a human
    # rep reviews + confirms. Pricing is whatever the partner's pricelist
    # yields (a fresh AI-agent lead is retail); the agent cannot set or
    # influence price.
    # ------------------------------------------------------------------
    def _create_draft_order(self, cleaned, partner, line_items):
        Order = self.env["sale.order"]
        agent_label = cleaned.get("agent_name") or _("AI agent")
        order_vals = {
            "partner_id": partner.id,
            # AI-agent provenance visible right on the quotation header /
            # every sales list — client_order_ref renders as "Customer
            # Reference" on the SO form and printout.
            "client_order_ref": "🤖 %s (%s)" % (
                _("AI-agent self-service quote"), agent_label),
        }
        # Tag the order too, when sale.order carries tag_ids (crm bridge).
        ai_tag = self.env.ref(
            "southbrook_agent_gateway.crm_tag_ai_agent",
            raise_if_not_found=False)
        if ai_tag and "tag_ids" in Order._fields:
            order_vals["tag_ids"] = [(4, ai_tag.id)]
        order = Order.create(order_vals)
        Sol = self.env["sale.order.line"]
        Variant = self.env["product.product"]
        for item in line_items:
            tmpl = item["template"]
            variant = tmpl.product_variant_ids[:1]
            if not variant:
                variant = Variant.create({"product_tmpl_id": tmpl.id})
            Sol.create({
                "order_id": order.id,
                "product_id": variant.id,
                "product_uom_qty": item["qty"],
            })
        # Flip draft -> sent (Submitted for Review), matching the portal
        # request_price flow. Stamp the submitted-date if the field is
        # present (southbrook_estimating adds it).
        write_vals = {"state": "sent"}
        if "southbrook_submitted_date" in order._fields:
            write_vals["southbrook_submitted_date"] = fields.Datetime.now()
        order.write(write_vals)
        order.message_post(body=_(
            "Draft quotation self-created via the AI-agent gateway. "
            "Customer contact info is UNVERIFIED until the email "
            "confirmation link is clicked."))
        return order

    def _create_lead(self, cleaned, partner, is_new_partner):
        source = self.env.ref(
            "southbrook_agent_gateway.utm_source_ai_agent",
            raise_if_not_found=False)
        medium = self.env.ref(
            "southbrook_agent_gateway.utm_medium_agent_api",
            raise_if_not_found=False)
        ai_tag = self.env.ref(
            "southbrook_agent_gateway.crm_tag_ai_agent",
            raise_if_not_found=False)
        agent_label = cleaned.get("agent_name") or _("an AI agent")
        details = [
            "*** " + _("AI-AGENT-SUBMITTED LEAD") + " ***",
            _("This lead was created automatically by %s on a customer's "
              "behalf via the Southbrook AI-agent gateway — NOT entered by "
              "a person. Confirm details on the person-to-person "
              "follow-up.") % agent_label,
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
        addr_bits = [cleaned.get(k) for k in
                     ("street", "city", "state_name", "zip_code",
                      "country_name")]
        addr = ", ".join(b for b in addr_bits if b)
        if addr:
            details.append(_("Address: %s") % addr)
        details.append("")
        details.append(_(
            "Contact info is UNVERIFIED until the customer clicks the "
            "verification email."))

        vals = {
            # AI-agent provenance is stamped in the lead NAME itself so it
            # is unmissable in every list/kanban view, not just the form.
            "name": "🤖 " + _("AI-agent lead — %s") % cleaned["customer_name"],
            "type": "lead",
            "partner_id": partner.id,
            "contact_name": cleaned["customer_name"],
            "email_from": cleaned["email"],
            # SECURITY (2026-07-05 code-review fix): Odoo syncs a lead's
            # phone/street/etc. back onto its linked partner when the
            # partner's own field is blank. For a REUSED (pre-existing)
            # contact that would let an unverified third-party submission
            # plant data on a real customer — so withhold every syncing
            # contact field unless WE created the partner this call.
            # crm.lead.description is an Html field: assemble the
            # attacker-controlled text as PLAIN text and convert with
            # plaintext2html so nothing is interpreted as markup (XSS).
            "description": plaintext2html("\n".join(details)),
            "source_id": source.id if source else False,
            "medium_id": medium.id if medium else False,
            "tag_ids": [(4, ai_tag.id)] if ai_tag else False,
        }
        if is_new_partner:
            vals["phone"] = cleaned["phone"] or False
            vals.update(self._partner_address_vals(cleaned))
        return self.env["crm.lead"].create(vals)

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
        recordset. Idempotent: re-clicking the link is a no-op success.

        The lookup is an indexed equality search (the token is a 256-bit
        urlsafe secret, so a SQL-index probe leaks no usable timing), but
        we still re-check the match with hmac.compare_digest as defence
        in depth against any future change to a non-constant-time store."""
        if not token or not isinstance(token, str) or len(token) > 128:
            return self.browse()
        inquiry = self.search([("verify_token", "=", token)], limit=1)
        if (not inquiry or inquiry.state == "spam"
                or not hmac.compare_digest(inquiry.verify_token or "", token)):
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
        payload = {
            "reference": self.reference,
            "state": self.state,
            "email_verified": self.state == "verified",
            "sales_stage": stage,
            "assigned": bool(self.lead_id and self.lead_id.user_id),
        }
        if self.sale_order_id:
            payload["quote"] = self.quote_summary()
        return payload

    def quote_summary(self):
        """Customer-safe summary of the draft quotation, or None. Prices
        are the order's own computed subtotals — no internal cost, margin
        or channel data ever leaves this method."""
        self.ensure_one()
        order = self.sale_order_id
        if not order:
            return None
        currency = order.currency_id.name or (
            self.env.company.currency_id.name or "CAD")
        return {
            "quote_reference": order.name,
            "currency": currency,
            "lines": [{
                "description": line.product_id.display_name,
                "sku": line.product_id.default_code or "",
                "qty": line.product_uom_qty,
                "unit_price": line.price_unit,
                "subtotal": line.price_subtotal,
            } for line in order.order_line if line.product_id],
            "subtotal": order.amount_untaxed,
            "total": order.amount_total,
            "status": "submitted_for_review",
            "note": (
                "This is an indicative retail quotation awaiting review "
                "by a Southbrook representative; final pricing may reflect "
                "configuration options and any applicable program "
                "discounts."),
        }
