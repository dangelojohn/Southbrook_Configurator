# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


SEVERITY_RANK = {"blocker": 0, "warning": 1, "info": 2}


class SouthbrookMiCheck(models.Model):
    _name = "southbrook.mi.check"
    _description = "Southbrook Manufacturing Intelligence Check"
    # Order by severity rank then category. Selection values sort by
    # stored string, so 'blocker'/'info'/'warning' alphabetical-DESC
    # produces warning > info > blocker — semantically wrong. We
    # store a numeric rank in `severity_rank` (compute below) and sort
    # by that, then by category for sibling-grouping.
    _order = "severity_rank asc, category, id"

    name = fields.Char(required=True)
    severity = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("blocker", "Blocker"),
        ],
        required=True,
        default="info",
        index=True,
    )
    category = fields.Selection(
        [
            ("cut", "Cut"),
            ("production", "Production"),
            ("assembly", "Assembly"),
            ("install", "Install"),
            ("cad", "CAD"),
            ("hardware", "Hardware"),
        ],
        required=True,
        default="production",
        index=True,
    )
    message = fields.Text(required=True)
    recommendation = fields.Text()
    production_id = fields.Many2one(
        "mrp.production", string="Manufacturing Order", ondelete="cascade", index=True
    )
    production_package_id = fields.Many2one(
        "sb.production.package", string="Production Package", ondelete="cascade", index=True
    )
    active = fields.Boolean(default=True)
    severity_rank = fields.Integer(
        compute="_compute_severity_rank", store=True, index=True,
        help="0 = blocker, 1 = warning, 2 = info. Used to drive _order so "
             "the list view shows the most urgent rows first.",
    )

    @api.depends("severity")
    def _compute_severity_rank(self):
        for rec in self:
            rec.severity_rank = SEVERITY_RANK.get(rec.severity, 99)
