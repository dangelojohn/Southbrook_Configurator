# SPDX-License-Identifier: LGPL-3.0-only
"""Extends SouthbrookOrderBuilderPortal with the send_to_production
action branch.

M3 + M7 — when the dealer-mode FooterActions component fires
/southbrook/api/order/<id>/action with action_code='send_to_production',
we land here, delegate to sale.order.action_send_to_production(),
and return the new MO ids.
"""
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from odoo.addons.southbrook_estimating_website.controllers.main import (
    SouthbrookOrderBuilderPortal,
)


class SouthbrookOrderBuilderPortalMRP(SouthbrookOrderBuilderPortal):

    def southbrook_api_order_action(self, order_id, action_code=None, **kw):
        if action_code != "send_to_production":
            return super().southbrook_api_order_action(
                order_id, action_code=action_code, **kw,
            )

        try:
            order = self._southbrook_resolve_order(order_id)
        except MissingError:
            return {"error": "not_found"}
        except AccessError:
            return {"error": "forbidden"}

        try:
            mos = order.with_user(request.env.user).sudo().action_send_to_production()
        except UserError as e:
            return {"error": "wrong_state", "message": str(e)}

        if not mos:
            return {
                "ok": False,
                "error": "no_bom_lines",
                "message": (
                    "No order lines had a resolvable BoM. Send-to-"
                    "Production requires at least one line whose "
                    "product variant maps to a normal-type BoM. "
                    "Check that the cabinet templates have been "
                    "seeded with routings via southbrook_mrp_pm."
                ),
            }

        return {
            "ok": True,
            "mo_ids": mos.ids,
            "mo_names": mos.mapped("name"),
            "redirect_url": (
                "/odoo/action-mrp.mrp_production_action/%s" % mos[0].id
            ),
        }
