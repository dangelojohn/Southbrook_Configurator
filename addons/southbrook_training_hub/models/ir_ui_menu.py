# SPDX-License-Identifier: LGPL-3.0-only
"""Extend ir.ui.menu with a backref so the Help systray can query it.

Tiny extension on purpose — the m2m is the only addition. The Help panel
calls ``ir.ui.menu.read([menu_id], ['training_item_ids'])`` to fetch
pinned items in one round-trip.
"""
from odoo import fields, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    training_item_ids = fields.Many2many(
        "southbrook.training.item",
        "southbrook_training_menu_link",
        "menu_id",
        "item_id",
        string="Pinned Training Items",
        compute="_compute_training_item_ids",
        store=False,
    )

    def _compute_training_item_ids(self):
        """Resolve pinned items via southbrook.training.menu_link.

        We don't reuse the menu_link table as a real m2m table because
        menu_link also carries sequence + note. A computed read is fine
        here — menus are cached client-side after first load.
        """
        Link = self.env["southbrook.training.menu_link"].sudo()
        for menu in self:
            links = Link.search([("menu_id", "=", menu.id)])
            menu.training_item_ids = links.mapped("item_id")
