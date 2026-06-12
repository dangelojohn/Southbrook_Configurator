# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    southbrook_exclude_from_pm_reports = fields.Boolean(
        string="Exclude from Southbrook PM Reports",
        copy=False,
        help="Use for confirmed demo/reference records. This does not delete "
             "the scrap record.")
    southbrook_cleanup_note = fields.Text(
        string="Southbrook Cleanup Note", copy=False)
