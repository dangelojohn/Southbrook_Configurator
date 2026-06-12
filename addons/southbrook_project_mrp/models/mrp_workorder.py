# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    southbrook_not_scheduled = fields.Boolean(
        string="Not Scheduled",
        compute="_compute_southbrook_not_scheduled",
        help="True when this work order has no planned/actual start date.")

    @api.depends("date_start")
    def _compute_southbrook_not_scheduled(self):
        for workorder in self:
            workorder.southbrook_not_scheduled = not bool(workorder.date_start)
