# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.shift.handover — digital handover log (SAMI PRD MES-10).

Replaces the paper handover notes that shift leads pass at change-of-shift.
Captures: who handed off to whom, which cells, what the state was, what
the incoming lead needs to know.

Core surface for the SAMI floor:
  - At change-of-shift (~7am / 3pm / 11pm), outgoing lead opens a new
    handover, lists workcenters under their watch, writes a summary
    (open WOs, holds, breakdowns, planned maintenance windows, etc.),
    and submits — incoming lead is auto-followered and gets it in
    their Odoo inbox.
  - Incoming lead reviews + acknowledges. The handover is sealed.
  - Both names + timestamps are immutable audit trail.

Not in scope for v1:
  - Auto-populate workcenter state (last WO completed, open downtimes)
    — would need careful per-cell snapshotting; valuable but Phase 4.
  - Acknowledgement is just a state transition; no per-line sign-off
    on individual notes.
  - Shift schedule integration — for v1 the shift selection is
    operator-chosen.
"""
from odoo import _, api, fields, models


SHIFT_SELECTION = [
    ("day", "Day"),
    ("evening", "Evening"),
    ("night", "Night"),
    ("weekend", "Weekend"),
]


HANDOVER_STATES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("acknowledged", "Acknowledged"),
    ("cancelled", "Cancelled"),
]


class SouthbrookShiftHandover(models.Model):
    _name = "southbrook.shift.handover"
    _description = "Southbrook Shift Handover Log"
    _inherit = ["mail.thread", "mail.activity.mixin", "southbrook.qr.mixin"]
    _order = "shift_date desc, id desc"
    _qr_kind = "shift"

    name = fields.Char(
        string="Reference",
        default=lambda self: _("New"),
        required=True,
        copy=False,
        readonly=True,
        index=True,
    )
    state = fields.Selection(
        HANDOVER_STATES,
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    shift = fields.Selection(
        SHIFT_SELECTION,
        string="Shift",
        required=True,
        tracking=True,
        index=True,
    )
    shift_date = fields.Date(
        string="Shift Date",
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    from_user_id = fields.Many2one(
        "res.users",
        string="Handed Off By",
        default=lambda s: s.env.user,
        required=True,
        tracking=True,
    )
    to_user_id = fields.Many2one(
        "res.users",
        string="Handed Off To",
        tracking=True,
        help="The incoming shift lead. Auto-followered when the "
             "handover is submitted so it lands in their Odoo inbox.",
    )
    workcenter_ids = fields.Many2many(
        "mrp.workcenter",
        "southbrook_shift_handover_wc_rel",
        "handover_id", "workcenter_id",
        string="Workcenters",
        help="The cells the outgoing lead was responsible for during "
             "this shift.",
    )
    # W087 (R2.7) — Structured shift-handover prompts.
    #
    # JTBD: zero handovers exist in production today; the free-text
    # `summary` field is the friction. Replacing freeform Text with
    # three yes/no triage questions + an optional notes field lowers
    # the cognitive load to "tap three Yes/No" so the outgoing lead
    # actually creates the record.
    #
    # The legacy `summary` field is kept (renamed to a Description
    # role) so existing handovers + searches keep working — the new
    # structured fields augment, not replace.
    q_anything_broken = fields.Boolean(
        string="Anything Broken?",
        tracking=True,
        help="Any equipment, fixture, jig, or tool that's currently "
             "out of service or running in a degraded state the "
             "incoming lead must know about.",
    )
    q_material_low = fields.Boolean(
        string="Material Running Low?",
        tracking=True,
        help="Any raw material, hardware, or consumable that is at "
             "or near reorder point and could starve the line during "
             "the incoming shift.",
    )
    q_safety_concern = fields.Boolean(
        string="Safety Concern?",
        tracking=True,
        help="Any near-miss, hazard, spill, blocked exit, or PPE "
             "issue from this shift the incoming lead must know "
             "about before sign-on.",
    )
    q_extra_notes = fields.Text(
        string="Extra Notes (Optional)",
        help="Free-text augment to the three triage questions. Use "
             "for anything that doesn't fit the Yes/No prompts.",
    )
    summary = fields.Text(
        string="Summary (Legacy / Description)",
        help="Pre-W087 free-text summary. New handovers should use "
             "the three structured triage questions + optional "
             "Extra Notes. Kept here for backward compatibility "
             "with historical records and search filters.",
        tracking=True,
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_shift_handover_attach_rel",
        "handover_id", "attachment_id",
        string="Attachments",
    )
    submitted_at = fields.Datetime(readonly=True, copy=False)
    acknowledged_at = fields.Datetime(readonly=True, copy=False)
    acknowledged_by = fields.Many2one(
        "res.users", readonly=True, copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.shift.handover") or _("SH/New")
        return super().create(vals_list)

    def action_submit(self):
        """Transition draft → submitted. Auto-follower the to_user_id
        so they get a chatter notification."""
        for rec in self:
            if rec.state != "draft":
                continue
            rec.write({
                "state": "submitted",
                "submitted_at": fields.Datetime.now(),
            })
            if rec.to_user_id:
                rec.message_subscribe(partner_ids=[
                    rec.to_user_id.partner_id.id])
            rec.message_post(
                body=_("Handover submitted by %s.") %
                self.env.user.display_name,
            )

    def action_acknowledge(self):
        """Transition submitted → acknowledged. Only the to_user_id (or
        a manager) should call this in practice; v1 doesn't enforce."""
        for rec in self:
            if rec.state != "submitted":
                continue
            rec.write({
                "state": "acknowledged",
                "acknowledged_at": fields.Datetime.now(),
                "acknowledged_by": self.env.user.id,
            })
            rec.message_post(
                body=_("Acknowledged by %s.") %
                self.env.user.display_name,
            )

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"
