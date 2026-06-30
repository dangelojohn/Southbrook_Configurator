# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.tool.usage — formal tool checkout/checkin audit.

Replaces the chatter-only QR checkout flow with a real record:
date, tool, workorder, who checked out, who checked in, duration,
condition. Auditors can now query "which tools were issued for
WO #5421?" and "what's the avg checkout duration for the trim saw?"
Feeds predictive-maintenance signals + tool-wear-per-operation-type
analysis.
"""
from odoo import _, api, fields, models


CONDITION_LEVELS = [
    ("ok", "OK"),
    ("worn", "Worn"),
    ("damaged", "Damaged"),
    ("missing", "Missing"),
]


class SouthbrookToolUsage(models.Model):
    _name = "southbrook.tool.usage"
    _description = "Southbrook Tool Usage Record"
    _inherit = ["mail.thread"]
    _order = "checked_out_at desc, id desc"

    name = fields.Char(
        compute="_compute_name", store=True, readonly=True,
        index=True,
    )
    tool_id = fields.Many2one(
        "southbrook.tool.asset",
        required=True, ondelete="cascade", index=True, tracking=True,
    )
    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Work Order", index=True, tracking=True,
        ondelete="set null",
    )
    production_id = fields.Many2one(
        related="workorder_id.production_id",
        store=True, readonly=True, index=True,
    )
    workcenter_id = fields.Many2one(
        related="workorder_id.workcenter_id",
        store=True, readonly=True,
    )
    checked_out_by = fields.Many2one(
        "res.users", required=True, default=lambda s: s.env.user,
        tracking=True,
    )
    checked_out_at = fields.Datetime(
        default=fields.Datetime.now, required=True, index=True,
        tracking=True,
    )
    checked_in_by = fields.Many2one(
        "res.users", tracking=True,
        help="The user who returned the tool. May differ from "
             "checked_out_by (operator handoff between shifts).",
    )
    checked_in_at = fields.Datetime(tracking=True, index=True)
    duration_min = fields.Float(
        string="Duration (min)",
        compute="_compute_duration", store=True, digits=(8, 2),
    )
    return_condition = fields.Selection(
        CONDITION_LEVELS, tracking=True,
        help="Condition the operator returned the tool in. Used by "
             "the predictive-maintenance analytics layer to flag "
             "tools trending toward 'damaged'.",
    )
    notes = fields.Text()

    @api.depends("tool_id", "workorder_id", "checked_out_at")
    def _compute_name(self):
        for rec in self:
            tool = rec.tool_id.display_name or "?"
            wo = rec.workorder_id.name or "no-WO"
            stamp = rec.checked_out_at.strftime("%Y-%m-%d %H:%M") if rec.checked_out_at else ""
            rec.name = f"{tool} → {wo} @ {stamp}"

    @api.depends("checked_out_at", "checked_in_at")
    def _compute_duration(self):
        for rec in self:
            if rec.checked_out_at and rec.checked_in_at:
                delta = rec.checked_in_at - rec.checked_out_at
                rec.duration_min = delta.total_seconds() / 60.0
            else:
                rec.duration_min = 0.0

    def action_checkin(self, condition=None):
        for rec in self:
            if rec.checked_in_at:
                continue
            vals = {
                "checked_in_at": fields.Datetime.now(),
                "checked_in_by": self.env.user.id,
            }
            if condition:
                vals["return_condition"] = condition
            rec.write(vals)
            rec.message_post(body=_("Returned by %s.") %
                             self.env.user.display_name)
