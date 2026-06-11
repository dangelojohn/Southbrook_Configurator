# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SouthbrookMiCheck(models.Model):
    _name = "southbrook.mi.check"
    _description = "Southbrook Manufacturing Intelligence Check"
    _order = "category, id"

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
