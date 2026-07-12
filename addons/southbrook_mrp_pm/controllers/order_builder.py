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
from odoo.tools.translate import _

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

        # Security (mirrors the parent's send_to_manufacturing guard, added in
        # the 2026-07-11 audit): releasing an order to the shop floor is a
        # STAFF action. _southbrook_resolve_order grants a portal
        # customer/dealer (share=True) access to their own order for review,
        # but the sudo() below runs as OdooBot — a share user must NOT be able
        # to create MOs. Reject share callers, and honour the production-
        # approval gate here too (defense-in-depth; the MO-create gate also
        # enforces it, but returning a clean 'not_approved' beats a UserError).
        if request.env.user.share:
            return {
                "error": "forbidden",
                "message": _("Only staff may send an order to production."),
            }
        if ("production_approval_state" in order._fields
                and order.production_approval_state != "approved"):
            return {
                "error": "not_approved",
                "message": _(
                    "Order has not passed production approval (state: %s)."
                ) % order.production_approval_state,
            }

        try:
            mos = order.with_user(request.env.user).sudo().action_send_to_production()
        except UserError as e:
            return {"error": "wrong_state", "message": str(e)}
        except AccessError:
            return {"error": "forbidden"}

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
