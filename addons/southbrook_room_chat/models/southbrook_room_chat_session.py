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

from odoo import fields, models

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


class SouthbrookRoomChatSession(models.Model):
    _name = "southbrook.room.chat.session"
    _description = "Southbrook AI Room Chat Session"
    _rec_name = "order_id"

    order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade", index=True)
    draft_json = fields.Text(
        default=lambda self: json.dumps(_BLANK_DRAFT))
    transcript_json = fields.Text(default="[]")

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

    def reset(self):
        """Clear both the draft and the transcript back to blank."""
        self.ensure_one()
        self.draft_json = json.dumps(json.loads(json.dumps(_BLANK_DRAFT)))
        self.transcript_json = "[]"

    def get_or_create_for_order(self, order_id):
        """env['southbrook.room.chat.session'].get_or_create_for_order(id)
        — return the (singleton) session for this order, creating a blank
        one if none exists yet."""
        session = self.search([("order_id", "=", order_id)], limit=1)
        if session:
            return session
        return self.create({"order_id": order_id})
