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
