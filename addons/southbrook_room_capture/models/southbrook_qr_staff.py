# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.qr.staff — INTERNAL (staff) QR lookup.

The sibling southbrook.qr.part model is deliberately CUSTOMER-SAFE — it
hides cost, manufacturing state, and shipping so a customer scanning
their own cabinet label sees only their quote. This model is the exact
opposite: it is for Southbrook INTERNAL staff (installers, shipping,
factory) who scan a cabinet's QR on their phone and need to see
EVERYTHING Southbrook knows about that physical package — which customer
and order it belongs to, its manufacturing status, its shipping/delivery
status, install placement, and the scan history.

READ-ONLY: it browses records and serializes; it never writes, never
advances a work order (that is southbrook_floor_traveler's shop-floor
scan path), and never creates anything. Access control is the caller's
job — the controller gates this route to INTERNAL users only (portal
customers must never reach it), and calls this model via .sudo() so the
serialization can read across MO / picking / cutlist regardless of the
individual staffer's per-model record rules.

Payload resolution is shared with the customer path: it reuses
southbrook.qr.part.resolve_package_id() (both QR formats, HMAC-checked
for the signed one) rather than re-implementing it.
"""
import json
import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

_PACKAGE_STATE_LABELS = {
    "draft": "Draft",
    "ready": "Ready for Shop Floor",
    "released": "Released to Production",
    "done": "Done",
}


class SouthbrookQrStaff(models.AbstractModel):
    _name = "southbrook.qr.staff"
    _description = "Southbrook QR Staff Lookup (internal, read-only)"

    # ------------------------------------------------------------------
    # Public entry point — payload string -> full internal info dict.
    # Never raises; returns {"ok": False, "error": <code>} on any miss.
    # ------------------------------------------------------------------
    @api.model
    def lookup(self, payload):
        pkg_id = self.env["southbrook.qr.part"].sudo().resolve_package_id(payload)
        if pkg_id is None:
            return {"ok": False, "error": "invalid"}
        package = self.env["sb.production.package"].sudo().browse(pkg_id).exists()
        if not package:
            return {"ok": False, "error": "not_found"}
        try:
            return {"ok": True, "info": self._serialize_internal(package)}
        except Exception as exc:  # noqa: BLE001 — never 500 a scanner
            _logger.warning(
                "southbrook.qr.staff: serialize failed for package %s: %s",
                pkg_id, exc)
            return {"ok": False, "error": "lookup_failed"}

    # ------------------------------------------------------------------
    # Full internal serialization. Every cross-model read is defensive
    # (getattr / hasattr) so the lookup still works on a deployment
    # missing an optional module (sale_stock, delivery, floor_traveler).
    # ------------------------------------------------------------------
    @api.model
    def _serialize_internal(self, package):
        package.ensure_one()
        line = package.sale_order_line_id
        order = line.order_id if line else self.env["sale.order"]
        partner = order.partner_id if order else self.env["res.partner"]

        info = {
            "package": self._package_block(package),
            "product": self._product_block(line),
            "customer": self._customer_block(order, partner),
            "placement": self._placement_block(line),
            "manufacturing": self._manufacturing_block(package),
            "shipping": self._shipping_block(order),
            "scan_history": self._scan_history_block(package),
        }
        return info

    # -- sub-blocks ----------------------------------------------------
    def _package_block(self, package):
        state = package.state
        return {
            "id": package.id,
            "name": package.name,
            "state": state,
            "state_label": _PACKAGE_STATE_LABELS.get(state, state or "—"),
            "pricing_pending": bool(
                getattr(package, "has_pricing_pending", False)),
        }

    def _product_block(self, line):
        if not line:
            return {}
        product = line.product_id
        return {
            "name": product.display_name if product else (line.name or "—"),
            "sku": product.default_code if product else "",
            "spec": line.name or "",
            "qty": line.product_uom_qty,
            "width_mm": getattr(line, "sb_width_mm", None),
            "panel_count": getattr(line, "sb_panel_count", None),
            "door_count": getattr(line, "sb_door_count", None),
        }

    def _customer_block(self, order, partner):
        if not order:
            return {}
        addr_parts = [partner.street, partner.street2, partner.city,
                      partner.state_id.name if partner.state_id else None,
                      partner.zip, partner.country_id.name
                      if partner.country_id else None]
        return {
            "order_id": order.id,
            "order_name": order.name,
            "order_state": order.state,
            "client_ref": order.client_order_ref or "",
            "partner_id": partner.id if partner else None,
            "partner_name": partner.name if partner else "—",
            "partner_phone": (partner.phone or partner.mobile or "")
            if partner else "",
            "partner_email": partner.email if partner else "",
            "address": ", ".join(p for p in addr_parts if p),
            "salesperson": order.user_id.name if order.user_id else "",
        }

    def _placement_block(self, line):
        if not line:
            return {}
        wall = getattr(line, "wall_id", None)
        return {
            "zone": getattr(line, "zone", None),
            "zone_label": getattr(line, "zone_label", None),
            "wall": wall.display_name if wall else None,
            "position_from_left_mm": getattr(
                line, "position_from_left_mm", None),
        }

    def _manufacturing_block(self, package):
        mo = getattr(package, "mo_id", None)
        block = {
            "package_state_label": _PACKAGE_STATE_LABELS.get(
                package.state, package.state or "—"),
            "cutlist": (package.cutlist_id.display_name
                        if getattr(package, "cutlist_id", False) else None),
            "hardware_package": (
                package.hardware_package_id.display_name
                if getattr(package, "hardware_package_id", False) else None),
        }
        if mo:
            block.update({
                "mo_name": mo.name,
                "mo_state": mo.state,
                "mo_date_planned": self._fmt_dt(
                    getattr(mo, "date_start", False)
                    or getattr(mo, "date_planned_start", False)),
                "mo_date_finished": self._fmt_dt(
                    getattr(mo, "date_finished", False)),
                "workorders": [{
                    "name": wo.display_name,
                    "workcenter": (wo.workcenter_id.name
                                   if wo.workcenter_id else "—"),
                    "state": wo.state,
                } for wo in getattr(mo, "workorder_ids", [])],
            })
        return block

    def _shipping_block(self, order):
        pickings = getattr(order, "picking_ids", None) if order else None
        if not pickings:
            return {"pickings": []}
        out = []
        for p in pickings:
            out.append({
                "name": p.name,
                "state": p.state,
                "scheduled_date": self._fmt_dt(
                    getattr(p, "scheduled_date", False)),
                "date_done": self._fmt_dt(getattr(p, "date_done", False)),
                "carrier": (p.carrier_id.name
                            if getattr(p, "carrier_id", False) else ""),
                "tracking": getattr(p, "carrier_tracking_ref", "") or "",
                "delivery_address": (p.partner_id.contact_address_complete
                                     if getattr(p, "partner_id", False)
                                     and hasattr(p.partner_id,
                                                 "contact_address_complete")
                                     else ""),
            })
        return {"pickings": out}

    def _scan_history_block(self, package):
        raw = getattr(package, "x_scan_log_json", None)
        if not raw:
            return []
        try:
            log = json.loads(raw)
        except (TypeError, ValueError):
            return []
        if not isinstance(log, list):
            return []
        # Newest first, cap to the last 20 so a heavily-scanned package
        # doesn't bloat the mobile payload.
        return list(reversed(log))[:20]

    @staticmethod
    def _fmt_dt(value):
        if not value:
            return None
        try:
            return value.strftime("%Y-%m-%d %H:%M")
        except AttributeError:
            return str(value)
