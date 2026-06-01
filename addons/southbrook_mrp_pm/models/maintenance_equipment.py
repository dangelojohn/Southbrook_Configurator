# SPDX-License-Identifier: LGPL-3.0-only
"""maintenance.equipment extension — Southbrook condition flag.

M13 (Manufacturing PM JTBD 2026-06-01): maintenance.equipment
already exposes MTBF / MTTR / estimated_next_failure (out of the
box), but it has no real-time 'Condition' field. The PM gap
analysis called this out — the PM can't see at a glance which
machines are at risk vs healthy, and the Floor Manager has no
quick toggle to flag a developing issue.

This commit adds:

    southbrook_condition              Selection: good / fair /
                                       watch / critical / offline
    southbrook_condition_note         freeform notes
    southbrook_condition_last_updated readonly stamp
    southbrook_condition_updated_by   readonly user reference

Tracking is enabled on condition + note so the maintenance.equipment
chatter records every change in the audit trail.

Phase 2 polish (out of scope for this commit):

  - M14: equipment → impacted MO chain. Lookup view that takes a
         condition='critical' or 'offline' equipment and surfaces
         every MO whose routing uses the equipment's work center
         + the affected sale.orders + delivery dates.
  - Floor Manager portal route exposing the condition pill +
         a single-tap upgrade/downgrade widget so the operator
         can flag without leaving the station (M16/M17).
  - Automation rule: condition transitions to 'critical' or
         'offline' fire a chatter post on every in-flight MO
         that depends on the equipment's work center.
"""
from odoo import _, api, fields, models


CONDITION_SELECTION = [
    ("good", "Good"),
    ("fair", "Fair"),
    ("watch", "Watch"),
    ("critical", "Critical"),
    ("offline", "Offline"),
]


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    southbrook_condition = fields.Selection(
        CONDITION_SELECTION,
        string="Condition",
        default="good",
        tracking=True,
        help=(
            "Floor-Manager-set health snapshot of this equipment.\n"
            " good     — running normally\n"
            " fair     — running, watching\n"
            " watch    — issues observed, schedule attention\n"
            " critical — degraded; affecting throughput\n"
            " offline  — out of service"
        ),
    )
    southbrook_condition_note = fields.Text(
        string="Condition Notes",
        tracking=True,
        help=(
            "Brief context for the current condition state — e.g. "
            "'edge bander hot-melt blocked, scheduled service Friday'."
        ),
    )
    southbrook_condition_last_updated = fields.Datetime(
        string="Condition Last Updated",
        readonly=True,
        copy=False,
        help="Set automatically when southbrook_condition changes.",
    )
    southbrook_condition_updated_by = fields.Many2one(
        "res.users",
        string="Condition Updated By",
        readonly=True,
        copy=False,
        help="User who set the current condition.",
    )

    def write(self, vals):
        if "southbrook_condition" in vals:
            vals["southbrook_condition_last_updated"] = fields.Datetime.now()
            vals["southbrook_condition_updated_by"] = self.env.user.id
        return super().write(vals)
