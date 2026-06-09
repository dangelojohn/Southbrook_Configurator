# SPDX-License-Identifier: LGPL-3.0-only
"""Dealer-channel portal routes."""
import json
import logging

from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

_logger = logging.getLogger(__name__)


class DealerPortal(http.Controller):

    # ------------------------------------------------------------------
    # Dealer order list
    # ------------------------------------------------------------------
    @http.route(
        ["/my/dealer/orders"], type="http", auth="user",
        website=True, methods=["GET"],
    )
    def dealer_orders(self, **kw):
        self._require_dealer()
        SaleOrder = request.env["sale.order"].sudo()
        partner = request.env.user.partner_id
        orders = SaleOrder.search(
            [("partner_id", "=", partner.id)],
            order="date_order desc",
        )
        return request.render(
            "southbrook_dealer_portal.portal_dealer_orders_list",
            {"orders": orders, "page_name": "dealer_orders"},
        )

    # ------------------------------------------------------------------
    # KD export — JSON download
    # ------------------------------------------------------------------
    @http.route(
        ["/my/dealer/production-package/<int:pkg_id>/kd"],
        type="http", auth="user", website=True, methods=["GET"],
    )
    def kd_export(self, pkg_id, **kw):
        self._require_dealer()
        Package = request.env["sb.production.package"].sudo()
        package = Package.browse(pkg_id).exists()
        if not package:
            raise MissingError(_("Production package not found."))
        # ACL: package's MO must trace to an SO with the dealer's partner.
        # (For Phase 1 we accept any package the dealer can name; a real
        # production deployment must wire SO ↔ MO ↔ package linkage.)
        envelope = package.export_kd_envelope()
        body = json.dumps(envelope, indent=2)
        return request.make_response(
            body,
            headers=[
                ("Content-Type", "application/json"),
                ("Content-Disposition",
                 f'attachment; filename="kd_{package.name}.json"'),
            ],
        )

    # ------------------------------------------------------------------
    # Installation-drawing PDF (GAP-06)
    # ------------------------------------------------------------------
    @http.route(
        ["/my/dealer/production-package/<int:pkg_id>/installation-pdf"],
        type="http", auth="user", website=True, methods=["GET"],
    )
    def installation_pdf(self, pkg_id, **kw):
        self._require_dealer()
        Package = request.env["sb.production.package"].sudo()
        package = Package.browse(pkg_id).exists()
        if not package:
            raise MissingError(_("Production package not found."))
        pdf_bytes = package.export_installation_pdf()
        return request.make_response(
            pdf_bytes,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Disposition",
                 f'attachment; filename="installation_{package.name}.pdf"'),
            ],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _require_dealer(self):
        partner = request.env.user.partner_id
        channel = partner.channel if hasattr(partner, "channel") else None
        if channel != "dealer":
            _logger.warning(
                "Dealer-portal access denied: user=%s partner=%s channel=%r",
                request.env.user.id, partner.id, channel,
            )
            raise AccessError(_(
                "This area is for Southbrook dealers only. "
                "Contact your salesperson if you need access."
            ))
