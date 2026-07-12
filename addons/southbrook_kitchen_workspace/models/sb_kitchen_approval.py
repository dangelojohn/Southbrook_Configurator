# SPDX-License-Identifier: LGPL-3.0-only
"""sb.kitchen.approval — approval records for the project lifecycle.

Four approval types map to the four formal hand-off gates:
  concept            customer accepts a concept
  design             customer accepts the detailed design
  eng_review         engineering passes (PLM gate)
  production_release manager releases the MO to the shop floor
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


APPROVAL_TYPES = [
    ("concept", "Concept"),
    ("design", "Design"),
    ("eng_review", "Engineering Review"),
    ("production_release", "Production Release"),
]

APPROVER_TYPES = [
    ("customer", "Customer"),
    ("designer", "Designer"),
    ("manager", "Manager"),
    ("engineering", "Engineering"),
]

APPROVAL_STATES = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]


class SbKitchenApproval(models.Model):
    _name = "sb.kitchen.approval"
    _description = "Southbrook Kitchen Approval"
    _order = "date_decided desc, id desc"
    _inherit = ["mail.thread"]

    project_id = fields.Many2one(
        "sb.kitchen.project", required=True, ondelete="cascade", index=True,
    )
    approval_type = fields.Selection(APPROVAL_TYPES, required=True)
    approver_id = fields.Many2one("res.users", string="Approver")
    approver_type = fields.Selection(APPROVER_TYPES, required=True)
    state = fields.Selection(
        APPROVAL_STATES, default="pending", tracking=True, required=True,
        index=True,
    )
    notes = fields.Text()
    date_decided = fields.Datetime(readonly=True, copy=False)

    def write(self, vals):
        # Integrity gate: the approval state may ONLY change through the
        # Approve/Reject actions below (which set the sb_approval_transition
        # flag). A direct ORM/UI write to `state` — e.g. flipping a rejected
        # approval back to approved, bypassing the pending-guard — is refused.
        if "state" in vals and not self.env.context.get(
                "sb_approval_transition"):
            raise UserError(_(
                "Approval state changes only through the Approve / Reject "
                "actions, not by direct edit."))
        return super().write(vals)

    def action_approve(self):
        for record in self:
            if record.state != "pending":
                raise UserError(_(
                    "Approval already decided (state=%s).") % record.state)
            record.with_context(sb_approval_transition=True).write({
                "state": "approved",
                "approver_id": self.env.user.id,
                "date_decided": fields.Datetime.now(),
            })

    def action_reject(self):
        for record in self:
            if record.state != "pending":
                raise UserError(_(
                    "Approval already decided (state=%s).") % record.state)
            record.with_context(sb_approval_transition=True).write({
                "state": "rejected",
                "approver_id": self.env.user.id,
                "date_decided": fields.Datetime.now(),
            })
