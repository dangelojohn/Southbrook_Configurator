# SPDX-License-Identifier: LGPL-3.0-only
"""Map ir.ui.menu rows → training items.

When the in-app Help panel opens on a backend page (say, Quality → NCRs),
it asks "what training is anchored to *this* menu?" — this model holds
the answers. Admins pin items here; if no link exists, the panel falls
back to a tag-based query against the action's model name.
"""
from odoo import fields, models


class SouthbrookTrainingMenuLink(models.Model):
    _name = "southbrook.training.menu_link"
    _description = "Menu → Training Item Pin"
    _order = "menu_id, sequence"

    menu_id = fields.Many2one(
        "ir.ui.menu", required=True, ondelete="cascade", index=True)
    item_id = fields.Many2one(
        "southbrook.training.item", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    note = fields.Char(
        help="Optional admin annotation — why this lesson is pinned here.")

    _menu_item_uniq = models.Constraint(
        'UNIQUE(menu_id, item_id)',
        "Same lesson pinned twice to the same menu — that's a typo.",
    )
