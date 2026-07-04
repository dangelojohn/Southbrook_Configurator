# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.qr.part — resolves a scanned Southbrook QR payload to its
sb.production.package and serializes CUSTOMER-SAFE fields for display on
the Order Lines estimate.

A customer/estimator scans the QR printed on a physical cabinet's
Floor-Traveler label. The frontend decodes it client-side (see
static/src/js/qr_scan.esm.js) and POSTs the raw decoded string to
controllers/main.py's /southbrook/api/order/<id>/scan-part route, which
delegates the parse + serialize work to this AbstractModel so it is
unit-testable without HTTP.

Dual payload format (mirrors addons/southbrook_floor_traveler/
controllers/scan_endpoint.py `_resolve_package_id()` — kept as an
independent re-implementation, not an import, so this read-only lookup
carries zero coupling to the floor-traveler controller module):

  * Legacy (printed on real cabinets today, unsigned):
      "sb-package:<id>"
  * Signed (qr_kit, future):
      "sb://pkg/<id>?t=<unix_ts>&s=<hmac>" — verified via
      env["southbrook.qr.payload"].parse(), which HMAC-checks the
      signature and returns a dict including
      {"kind": "pkg", "ident": <int>, "valid_signature": bool, ...}.

This model is READ-ONLY end to end: resolve_package_id() only browses
sb.production.package (never creates/writes), and it NEVER calls
record_scan() / advances work orders the way
southbrook_floor_traveler's shop-floor scan endpoint does. Ownership
enforcement against the scanned package's own sale order happens in the
controller (which has access to `_southbrook_resolve_order` via the
`_SouthbrookOrderAccessMixin`) — this model does no ACL work of its own
and must always be called via .sudo() by a caller that has already
authorized the request.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class SouthbrookQrPart(models.AbstractModel):
    _name = "southbrook.qr.part"
    _description = "Southbrook QR Part Lookup (read-only)"

    # ------------------------------------------------------------------
    # Resolve: payload string -> sb.production.package id (or None)
    # ------------------------------------------------------------------
    @api.model
    def resolve_package_id(self, payload):
        """Parse EITHER QR payload format and return the target
        sb.production.package id, or None when the payload is not a
        non-empty string, doesn't match either scheme, or (signed
        format) fails HMAC verification / isn't kind "pkg".

        Never raises — a malformed/forged/wrong-kind payload is simply
        an unresolved lookup, not an exception, so the controller can
        turn it into a flat `{"error": "invalid"}` without a try/except
        of its own.
        """
        if not payload or not isinstance(payload, str):
            return None

        if payload.startswith("sb-package:"):
            try:
                return int(payload.split(":", 1)[1])
            except (TypeError, ValueError):
                return None

        if payload.startswith("sb://"):
            Payload = self.env.get("southbrook.qr.payload")
            if Payload is None:
                return None  # southbrook_qr_kit not installed
            try:
                parsed = Payload.sudo().parse(payload)
            except Exception:  # noqa: BLE001 — malformed payload, never raise
                return None
            if parsed.get("kind") == "pkg" and parsed.get("valid_signature"):
                try:
                    return int(parsed["ident"])
                except (TypeError, ValueError):
                    return None
            return None

        return None

    # ------------------------------------------------------------------
    # Serialize: sb.production.package -> customer-safe dict
    # ------------------------------------------------------------------
    @api.model
    def serialize(self, package, order_id):
        """Build the customer-safe response payload for a resolved
        sb.production.package.

        CUSTOMER-SAFE fields returned (quote number, product identity,
        spec text, dimensions, zone, qty, and the customer's OWN
        price_unit/price_subtotal — all values the customer already
        sees on their own quote document):
          part.product: {id, name, default_code}
          part.name                 — the line's spec text
          part.product_uom_qty
          part.price_unit / part.price_subtotal
          part.zone / part.zone_label
          part.wall_id: {id, name} or None
          part.position_from_left_mm
          part.sb_panel_count / part.sb_door_count / part.sb_width_mm

        Deliberately EXCLUDED — never returned to a customer:
          * Any cost/margin/purchase-price field (e.g. standard_price,
            purchase price, margin, cost_subtotal) — these would leak
            Southbrook's internal cost structure / vendor pricing to
            the person reading their own quote.
          * Manufacturing-intelligence / shop-floor internals:
            package.state, package.mo_id, package.cutlist_id,
            package.hardware_package_id, package.has_pricing_pending,
            and (from southbrook_floor_traveler) x_scan_log_json /
            qr_payload / qr_image_base64. None of these have
            customer-facing meaning; several (has_pricing_pending,
            state) are blocker/yield signals that would expose
            production bottlenecks or vendor-pricing gaps.
          * order.state / order.partner_id — the caller already knows
            which order they're looking at; only order.name (the quote
            number) is surfaced.

        :param package: a `sb.production.package` recordset (ensure_one).
        :param order_id: the route's own <order_id>, used only to
            compute `in_current_order` (whether the scanned cabinet
            belongs to the order currently open in the Order Lines
            estimate, so the frontend can highlight the matching line
            vs. show a "this part belongs to a different quote" note).
        :returns: dict with keys `part`, `line_id`, `quote_number`,
            `in_current_order`.
        """
        package.ensure_one()
        line = package.sale_order_line_id
        order = line.order_id if line else self.env["sale.order"]

        part = {
            "product": {
                "id": line.product_id.id if line and line.product_id else None,
                "name": line.product_id.name if line and line.product_id else None,
                "default_code": (
                    line.product_id.default_code
                    if line and line.product_id else None
                ),
            },
            "name": line.name if line else None,
            "product_uom_qty": line.product_uom_qty if line else None,
            "price_unit": line.price_unit if line else None,
            "price_subtotal": line.price_subtotal if line else None,
            "zone": line.zone if line else None,
            "zone_label": line.zone_label if line else None,
            "wall_id": (
                {"id": line.wall_id.id, "name": line.wall_id.display_name}
                if line and line.wall_id else None
            ),
            "position_from_left_mm": (
                line.position_from_left_mm if line else None
            ),
            "sb_panel_count": line.sb_panel_count if line else None,
            "sb_door_count": line.sb_door_count if line else None,
            "sb_width_mm": line.sb_width_mm if line else None,
        }
        return {
            "part": part,
            "line_id": line.id if line else None,
            "quote_number": order.name if order else None,
            "in_current_order": bool(order and order.id == order_id),
        }
