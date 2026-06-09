# SPDX-License-Identifier: LGPL-3.0-only
"""sb.kitchen.design.option — one concept design among A/B/C."""
from odoo import _, api, fields, models


class SbKitchenDesignOption(models.Model):
    _name = "sb.kitchen.design.option"
    _description = "Southbrook Kitchen Design Option"
    _order = "project_id, sequence, id"

    project_id = fields.Many2one(
        "sb.kitchen.project", required=True, ondelete="cascade", index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, help="e.g. 'Option A — Coastal Walnut'")
    description = fields.Html()
    preview_attachment_id = fields.Many2one(
        "ir.attachment", string="Visual Preview",
        domain="[('res_model', '=', 'sb.kitchen.design.option')]",
    )
    estimated_price = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    estimated_lead_time_days = fields.Integer()
    is_selected = fields.Boolean(
        string="Customer-Selected",
        help="Selecting this option flips other options on the same "
             "project to is_selected=False automatically.",
    )
    placement_data_json = fields.Text(
        string="Placement Data (JSON)",
        help="Module-7 configuration-engine output for this option. "
             "Empty until the config engine has placed cabinets.",
    )

    def write(self, vals):
        """One-of-N enforcement: when is_selected flips to True on a
        record, every other design_option on the same project flips to
        False atomically."""
        res = super().write(vals)
        if vals.get("is_selected"):
            for option in self.filtered("is_selected"):
                siblings = self.search([
                    ("project_id", "=", option.project_id.id),
                    ("id", "!=", option.id),
                    ("is_selected", "=", True),
                ])
                if siblings:
                    siblings.write({"is_selected": False})
        return res
