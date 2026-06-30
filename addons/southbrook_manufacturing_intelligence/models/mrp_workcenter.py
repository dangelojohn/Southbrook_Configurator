# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    x_mi_workcenter_blocker_count = fields.Integer(
        string="MI Blocked MOs",
        compute="_compute_southbrook_mi_kpis",
        help="Manufacturing orders touching this workcenter with active MI blockers.",
    )
    x_mi_workcenter_warning_count = fields.Integer(
        string="MI Warnings",
        compute="_compute_southbrook_mi_kpis",
        help="Total MI warnings on manufacturing orders touching this workcenter.",
    )

    # Non-stored snapshot — depends_context('uid') so the values are
    # re-aggregated on every form/kanban open by the requesting user.
    # We deliberately do NOT store these because the field is an
    # aggregate over a large MRP graph that changes constantly; storing
    # would require depends on every MI/MO state transition, which is
    # heavier than just re-aggregating at view time. Trade-off: kanban
    # cards opened mid-shift won't tick down until the user reloads
    # the view. Document this on both fields so a future maintainer
    # doesn't "fix" it by adding store=True (which would deadlock the
    # MO save path during high-throughput shifts).
    @api.depends_context("uid")
    def _compute_southbrook_mi_kpis(self):
        for workcenter in self:
            productions = self.env["mrp.production"].sudo().search(
                [
                    ("state", "not in", ["done", "cancel"]),
                    ("workorder_ids.workcenter_id", "=", workcenter.id),
                ]
            )
            workcenter.x_mi_workcenter_blocker_count = len(
                productions.filtered(lambda mo: mo.x_mi_blocker_count > 0)
            )
            workcenter.x_mi_workcenter_warning_count = sum(
                productions.mapped("x_mi_warning_count")
            )
