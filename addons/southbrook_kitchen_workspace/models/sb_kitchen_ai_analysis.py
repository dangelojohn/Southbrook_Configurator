# SPDX-License-Identifier: LGPL-3.0-only
"""sb.kitchen.ai.analysis — Gemini's room understanding for one project.

Module 6 (`southbrook_ai_design`) will produce these records; Module 5
just stores the schema. The confirmed_by_human boolean is the
gating contract — downstream consumers (the config engine, the cutlist
generator) MUST refuse to act when it's False (init-doc GAP-02)."""
from odoo import fields, models


class SbKitchenAiAnalysis(models.Model):
    _name = "sb.kitchen.ai.analysis"
    _description = "Southbrook Kitchen AI Room Analysis"
    _inherit = ["mail.thread"]
    _order = "date_analyzed desc, id desc"

    project_id = fields.Many2one(
        "sb.kitchen.project", required=True, ondelete="cascade", index=True,
    )
    date_analyzed = fields.Datetime(default=fields.Datetime.now, readonly=True)

    confirmed_by_human = fields.Boolean(
        tracking=True,
        help="Set to True only after a human designer has reviewed every "
             "dimensional field and confirmed it is accurate. Downstream "
             "consumers refuse to run while any required dimension is "
             "unconfirmed — init-doc GAP-02.",
    )
    confirmed_by_user_id = fields.Many2one(
        "res.users", readonly=True, copy=False,
    )
    confirmed_at = fields.Datetime(readonly=True, copy=False)

    raw_response_json = fields.Text(
        string="Gemini Raw Response (JSON)",
        help="Exact body Gemini returned — kept for audit + reprocessing.",
    )

    # Detected room facts (always approximate per init-doc GAP-02 — these
    # MUST be confirmed by a human before being trusted).
    sink_detected = fields.Boolean(tracking=True)
    window_count = fields.Integer(default=0)
    room_door_count = fields.Integer(
        string="Room Door Count", default=0,
        help="Doors INTO the room, not cabinet doors.",
    )
    floor_area_m2_approx = fields.Float(string="Floor Area (m²)", digits=(6, 2))
    ceiling_height_mm_approx = fields.Float(string="Ceiling Height (mm)")

    detected_appliances_json = fields.Text(
        help="JSON list of appliances Gemini saw, before sb.kitchen.appliance "
             "records are created from them.",
    )
    detected_dimensions_json = fields.Text(
        help="JSON of Gemini's per-dimension estimates with confidence scores.",
    )

    def action_confirm(self):
        """Mark this analysis confirmed. Stamps user + timestamp."""
        for record in self:
            record.write({
                "confirmed_by_human": True,
                "confirmed_by_user_id": self.env.user.id,
                "confirmed_at": fields.Datetime.now(),
            })

    def action_unconfirm(self):
        """Re-open the confirmation gate (e.g. dimensions changed)."""
        for record in self:
            record.write({
                "confirmed_by_human": False,
                "confirmed_by_user_id": False,
                "confirmed_at": False,
            })
