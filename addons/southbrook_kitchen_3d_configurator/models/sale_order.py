# SPDX-License-Identifier: LGPL-3.0-only
"""Recommendation D — Sprint 2c · sale.order "Open in 3D" action.

Wires the form button in views/rec_d_sale_order_views.xml. Reverse-
looks-up a design linked via sale_order_id; if none, falls back to
the SO's room's own action; if neither, spins up a bare configurator
pre-loaded with the partner. Zero data mutation — pure navigation.
"""

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_open_in_kitchen_3d(self):
        """Rec D Sprint 2c · direct jump from an SO to the 3D scene.

        Preference order:
        1. If a southbrook.kitchen.design has this SO's id in its
           sale_order_id — open its configurator (fully-populated
           scene with the design's saved cabinet layout).
        2. If the SO has a linked southbrook.room but no design —
           delegate to room.action_open_kitchen_3d (opens a scene
           pre-loaded with the room's dims + partner).
        3. If neither — open a bare configurator with just the SO's
           partner pre-set so channel pricing is right from step 1.
        """
        self.ensure_one()
        Design = self.env["southbrook.kitchen.design"]
        design = Design.search([("sale_order_id", "=", self.id)], limit=1)
        if design:
            return design.action_open_configurator()
        room = self.room_ids[:1]
        if room:
            return room.action_open_kitchen_3d()
        return {
            "type":   "ir.actions.client",
            "tag":    "southbrook_kitchen_configurator",
            "params": {
                "partner_id": self.partner_id.id if self.partner_id else False,
            },
        }
