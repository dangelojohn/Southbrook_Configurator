# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.room.chat.session — per-order conversation state.

One session per order (get-or-create keyed by order_id, mirroring the
"single room per order" convention already used by southbrook.room). Holds
the in-progress DRAFT room geometry (as plain JSON, in the exact shape
southbrook.room.capture._estimate_to_existing_room already produces) and a
lightweight plain-text transcript. Tool-call content blocks are resolved
fully within a single HTTP turn by southbrook.room.chat.agent and are never
replayed across turns, so only human-readable turns need to survive here.

This model NEVER creates southbrook.room / .wall / .constraint records —
the draft it stores is only ever handed to the frontend as a pre-fill
suggestion for the existing "Set Up Your Room" wizard.
"""
import json

from psycopg2 import IntegrityError

from odoo import _, fields, models
from odoo.tools import plaintext2html

_SHAPE_LABELS = {
    "straight": "straight run", "l_shape": "L-shaped", "u_shape": "U-shaped",
    "galley": "galley", "g_shape": "G-shaped", "island": "island",
    "peninsula": "peninsula", "custom": "custom",
}

_BLANK_DRAFT = {
    "name": "Main Kitchen",
    "room_type": "kitchen",
    "layout_shape": None,
    "ceiling_height_mm": 2400,
    "unit_preference": "mm",
    "walls": [],
    "assumptions": [],
    "warnings": [],
    "confidence": 0.0,
}

# v2 (2026-07-05): the customer profile the chat gathers conversationally
# for Contacts + CRM follow-up. Kept SEPARATE from the room draft so the
# geometry pre-fill contract to the Room Setup wizard is unchanged.
_BLANK_CUSTOMER = {
    "name": "",
    "email": "",
    "phone": "",
    "street": "",
    "city": "",
    "state_name": "",
    "zip_code": "",
    "country_name": "",
    "room_type": "",
    "budget_range": "",
    "timeline": "",
    "project_notes": "",
}


class SouthbrookRoomChatSession(models.Model):
    _name = "southbrook.room.chat.session"
    _description = "Southbrook AI Room Chat Session"
    _rec_name = "order_id"

    order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade", index=True)
    draft_json = fields.Text(
        default=lambda self: json.dumps(_BLANK_DRAFT))
    transcript_json = fields.Text(default="[]")
    # v2 — gathered customer profile (JSON) + the CRM lead once created,
    # so a second "save for follow-up" turn updates the same lead rather
    # than spawning duplicates.
    customer_json = fields.Text(
        default=lambda self: json.dumps(_BLANK_CUSTOMER))
    lead_id = fields.Many2one(
        "crm.lead", ondelete="set null", index=True)

    _order_id_uniq = models.Constraint(
        "UNIQUE(order_id)",
        "Each order can have at most one AI room-chat session.",
    )

    def get_draft(self):
        """Return the current draft as a plain dict. Never raises — a
        corrupted/empty value falls back to a blank draft."""
        self.ensure_one()
        try:
            draft = json.loads(self.draft_json or "")
        except (ValueError, TypeError):
            draft = None
        if not isinstance(draft, dict):
            draft = json.loads(json.dumps(_BLANK_DRAFT))
        return draft

    def set_draft(self, draft):
        """Persist `draft` (a plain dict) as the session's current draft."""
        self.ensure_one()
        self.draft_json = json.dumps(draft)

    def get_transcript(self):
        """Return the transcript as a list of {"role", "content"} dicts."""
        self.ensure_one()
        try:
            transcript = json.loads(self.transcript_json or "")
        except (ValueError, TypeError):
            transcript = None
        return transcript if isinstance(transcript, list) else []

    def append_turn(self, role, content):
        self.ensure_one()
        transcript = self.get_transcript()
        transcript.append({"role": role, "content": content})
        self.transcript_json = json.dumps(transcript)

    def get_customer(self):
        """Return the gathered customer profile as a plain dict, blank
        keys filled so callers never KeyError on a partially-gathered
        profile."""
        self.ensure_one()
        try:
            data = json.loads(self.customer_json or "")
        except (ValueError, TypeError):
            data = None
        merged = json.loads(json.dumps(_BLANK_CUSTOMER))
        if isinstance(data, dict):
            merged.update({k: data.get(k, merged[k]) for k in merged})
        return merged

    def set_customer(self, customer):
        self.ensure_one()
        self.customer_json = json.dumps(customer)

    def reset(self):
        """Clear the draft, transcript and gathered profile back to
        blank. The created lead_id is deliberately NOT unlinked — a real
        CRM lead a rep may already be working stays put; only the
        conversation state resets."""
        self.ensure_one()
        self.draft_json = json.dumps(json.loads(json.dumps(_BLANK_DRAFT)))
        self.transcript_json = "[]"
        self.customer_json = json.dumps(json.loads(json.dumps(_BLANK_CUSTOMER)))

    # ------------------------------------------------------------------
    # v2 — CRM hand-off. The ONE write path off the chat: enrich the
    # customer's OWN contact (they're authenticated in their own session,
    # so backfilling their blank fields is legitimate — unlike the
    # unauthenticated AI-agent gateway, which must never write to an
    # existing contact) and create/update a crm.lead so a live designer
    # follows up. Called by the agent's save_lead_for_followup tool.
    # ------------------------------------------------------------------
    def _room_summary_text(self, draft):
        shape = _SHAPE_LABELS.get(draft.get("layout_shape"),
                                  draft.get("layout_shape") or "unspecified")
        walls = draft.get("walls") or []
        lines = ["Room: %s, %d wall(s)." % (shape, len(walls))]
        for i, w in enumerate(walls):
            label = w.get("name") or ("Wall %s" % chr(ord("A") + (i % 26)))
            length = w.get("length_mm") or 0
            piece = "  - %s: %d mm" % (label, length)
            cons = w.get("constraints") or []
            if cons:
                piece += " (" + ", ".join(
                    "%s @ %dmm" % (c.get("constraint_type", "?"),
                                   c.get("distance_from_left_mm", 0))
                    for c in cons) + ")"
            lines.append(piece)
        ch = draft.get("ceiling_height_mm")
        if ch:
            lines.append("  Ceiling height: %d mm" % ch)
        return "\n".join(lines)

    def _save_followup_lead(self, customer, draft):
        self.ensure_one()
        order = self.order_id
        partner = order.partner_id
        Inquiry = self.env["southbrook.agent.inquiry"].sudo()

        # Enrich the customer's own contact — backfill BLANKS only, never
        # overwrite existing identity.
        addr_vals = Inquiry._partner_address_vals(customer)
        partner_updates = {}
        if not partner.phone and customer.get("phone"):
            partner_updates["phone"] = customer["phone"]
        for key in ("street", "city", "zip", "country_id", "state_id"):
            if addr_vals.get(key) and not partner[key]:
                partner_updates[key] = addr_vals[key]
        if partner_updates:
            partner.sudo().write(partner_updates)

        # Description — assemble plain text, convert to safe HTML (the
        # crm.lead.description field is Html).
        details = [
            "*** " + _("KITCHEN PLANNER CHAT LEAD (AI-assisted)") + " ***",
            _("Captured via Southbrook's 'Chat to build your room' "
              "designer. The customer asked to be contacted about their "
              "quote."),
            "",
            self._room_summary_text(draft),
            "",
        ]
        for label, key in (
            (_("Room type"), "room_type"),
            (_("Budget range"), "budget_range"),
            (_("Timeline"), "timeline"),
            (_("Notes"), "project_notes"),
        ):
            if customer.get(key):
                details.append("%s: %s" % (label, customer[key]))
        addr = ", ".join(customer.get(k) for k in (
            "street", "city", "state_name", "zip_code", "country_name")
            if customer.get(k))
        if addr:
            details.append(_("Address: %s") % addr)
        details.append("")
        details.append(_("Order: %s") % (order.name or order.id))

        source = self.env.ref(
            "southbrook_room_chat.utm_source_room_chat",
            raise_if_not_found=False)
        medium = self.env.ref(
            "southbrook_room_chat.utm_medium_room_chat",
            raise_if_not_found=False)
        ai_tag = self.env.ref(
            "southbrook_agent_gateway.crm_tag_ai_agent",
            raise_if_not_found=False)

        vals = {
            "name": "💬 " + _("Kitchen Planner chat — %s") % customer["name"],
            "type": "lead",
            "partner_id": partner.id,
            "contact_name": customer["name"],
            "email_from": customer["email"],
            "phone": customer.get("phone") or False,
            "description": plaintext2html("\n".join(details)),
            "source_id": source.id if source else False,
            "medium_id": medium.id if medium else False,
            "tag_ids": [(4, ai_tag.id)] if ai_tag else False,
        }
        if self.lead_id:
            self.lead_id.sudo().write(vals)
            return self.lead_id
        lead = self.env["crm.lead"].sudo().create(vals)
        self.lead_id = lead.id
        return lead

    def get_or_create_for_order(self, order_id):
        """env['southbrook.room.chat.session'].get_or_create_for_order(id)
        — return the (singleton) session for this order, creating a blank
        one if none exists yet.

        Race-safe: two concurrent requests for the same order (two open
        tabs, a client retry) can both pass the search below and both
        attempt create() — the UNIQUE(order_id) constraint rejects the
        loser, which is caught here and re-resolved to the winner's row
        rather than silently stranding the loser's draft on an orphan
        session no future call will ever find again.
        """
        session = self.search([("order_id", "=", order_id)], limit=1)
        if session:
            return session
        try:
            with self.env.cr.savepoint():
                return self.create({"order_id": order_id})
        except IntegrityError:
            return self.search([("order_id", "=", order_id)], limit=1)
