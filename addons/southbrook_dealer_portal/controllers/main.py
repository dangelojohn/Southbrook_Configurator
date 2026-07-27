# SPDX-License-Identifier: LGPL-3.0-only
"""Dealer-channel portal routes."""
import json
import logging
import re

from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

_logger = logging.getLogger(__name__)


def _safe_filename_part(value):
    """Sanitize a value interpolated into a Content-Disposition filename —
    strip quotes / CR / LF so a crafted package name can't break out of the
    filename or inject a header."""
    return re.sub(r'[^\w.\- ]', "_", (value or "")).strip() or "package"


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
        package = self._fetch_owned_package(pkg_id)
        envelope = package.export_kd_envelope()
        body = json.dumps(envelope, indent=2)
        fname = _safe_filename_part("kd_%s" % package.name)
        return request.make_response(
            body,
            headers=[
                ("Content-Type", "application/json"),
                ("Content-Disposition",
                 'attachment; filename="%s.json"' % fname),
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
        package = self._fetch_owned_package(pkg_id)
        pdf_bytes = package.export_installation_pdf()
        fname = _safe_filename_part("installation_%s" % package.name)
        return request.make_response(
            pdf_bytes,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Disposition",
                 'attachment; filename="%s.pdf"' % fname),
            ],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _fetch_owned_package(self, pkg_id):
        """Return the package IFF it traces to one of the acting dealer's own
        sale orders. Object-level authorization on top of _require_dealer's
        channel gate — WITHOUT this, a dealer could enumerate pkg ids and
        download every other customer's KD envelope / installation PDF (the
        record rule that should back-stop it was an empty domain). Collapse to
        the same not-found response for missing and not-owned, so package
        existence isn't leaked."""
        package = request.env["sb.production.package"].sudo().browse(pkg_id).exists()
        if not package or not package._belongs_to_partner(
                request.env.user.partner_id):
            if package:
                _logger.warning(
                    "Dealer-portal IDOR blocked: user=%s partner=%s tried "
                    "package %s (not owned).",
                    request.env.user.id, request.env.user.partner_id.id, pkg_id)
            raise MissingError(_("Production package not found."))
        return package

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
