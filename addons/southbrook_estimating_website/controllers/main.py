# SPDX-License-Identifier: LGPL-3.0-only
"""
Portal routes for the Southbrook Estimating Order Builder.

Track 2 commit 1 (2026-05-30) — Phase 2 charter amendment 1:
this is the SCAFFOLD route. Renders a portal page with the chrome,
breadcrumbs, sidebar, and an empty `<div id="order_builder_root">`
placeholder where commit 2 will mount the OWL `<OrderBuilder/>`
component tree.

The controller intentionally leaves the OWL bundle off the page in
this commit so we can verify the portal frame, auth, and routing
work cleanly before adding the JavaScript layer. Commit 2 adds the
OWL bundle to the manifest's assets section and switches this
template to inherit the bundle.

Route shape: `/my/southbrook/order-builder/<int:order_id>`
  Matches Odoo portal convention (`/my/...`) so portal-side menu
  hooks + breadcrumbs work without bespoke wiring.

Auth model: portal user; `partner_id.parent_id` chain identifies
the dealer. The controller verifies the order belongs to either
the logged-in partner OR the partner's parent (dealer org).
"""
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class SouthbrookOrderBuilderPortal(CustomerPortal):
    """Portal route hosting the OWL Order Builder."""

    # T2C1 NF: website=True is required after all. The portal layout
    # template (portal.frontend_layout, called via portal.portal_layout)
    # references the `website` variable in scope, so without
    # website=True the render aborts with KeyError: 'website'.
    # With website=True Odoo injects the current website record (id 1
    # "My Website" on the southbrook stack) into the template context.
    @http.route(
        ["/my/southbrook/order-builder",
         "/my/southbrook/order-builder/<int:order_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def southbrook_order_builder(self, order_id=None, **kw):
        """Render the Order Builder portal page.

        Without order_id: shows the dealer's list of open orders so
        they can pick one (Phase 2 commit 3 polish).

        With order_id: validates access (the partner OR their parent
        partner must own the order), then renders the OWL mount-point
        template with the order context.
        """
        order = None
        if order_id is not None:
            try:
                order = self._southbrook_resolve_order(order_id)
            except (AccessError, MissingError):
                return request.redirect("/my")

        values = self._prepare_southbrook_portal_values(order)
        return request.render(
            "southbrook_estimating_website.portal_order_builder",
            values,
        )

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _southbrook_resolve_order(self, order_id):
        """Look up the sale.order and check the user has access.

        Access rule:

          • Internal users (admin, sales reps, anyone whose
            res.users.share is False) see every order — they're
            staff with full backend access anyway, the portal page
            is just an alternate presentation.

          • Portal users (res.users.share=True — customers and
            dealers logged in via the public portal): the logged-in
            partner must equal order.partner_id, OR order.partner_id
            .parent_id must equal the logged-in partner (dealer
            views customer order), OR the logged-in partner's
            parent_id must equal order.partner_id (parent partner
            views child's order).

          • Anything else → AccessError, controller redirects to /my.
        """
        order = request.env["sale.order"].sudo().browse(order_id).exists()
        if not order:
            raise MissingError("Sale order not found.")

        user = request.env.user
        if not user.share:
            # Internal user — full access.
            return order

        my_partner = user.partner_id
        order_partner = order.partner_id
        if my_partner == order_partner:
            return order
        if order_partner.parent_id and order_partner.parent_id == my_partner:
            return order
        if my_partner.parent_id and my_partner.parent_id == order_partner:
            return order
        # Phase 3: dealer-portal page lists every order under the
        # dealer's whole partner tree; for commit 1 we keep access
        # tight to the same partner or first-level parent/child.
        raise AccessError("This order is not accessible to your account.")

    def _prepare_southbrook_portal_values(self, order):
        """Common template context (sidebar, breadcrumb, palette tokens)."""
        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "southbrook_order_builder",
            "order": order,
            "order_id": order.id if order else None,
            "order_name": order.name if order else "New Order",
            "user_partner": request.env.user.partner_id,
            # Track 2 commits 2+ will add an "owl_mount_id" used by the
            # OWL bootstrap to find its mount point on the page.
            "owl_mount_id": "order_builder_root",
        })
        return values
