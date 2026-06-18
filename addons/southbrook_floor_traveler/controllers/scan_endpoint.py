# SPDX-License-Identifier: LGPL-3.0-only
"""P8 — Workcenter scan endpoint.

POST /southbrook/api/floor-traveler/scan
  { "qr_payload": "sb-package:<id>", "workcenter_code": "<wc>" }

Returns:
  { "ok": True, "wo_id": int|null, "wo_state": "...", "scan_count": int }

The audit's load-bearing acceptance: a simulated scan -> button_finish
drives the existing tool-consumption debit *exactly once* — no
duplicate telemetry from re-implementing the debit here. We just call
the existing override.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class FloorTravelerScanAPI(http.Controller):

    @http.route(
        "/southbrook/api/floor-traveler/scan",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def floor_traveler_scan(self, qr_payload=None, workcenter_code=None, **kw):
        """Receive a scan event from the shop floor.

        :param qr_payload: the QR's decoded text — "sb-package:<id>".
        :param workcenter_code: free-text identifier of the scanning
            station (e.g. "PANEL-SAW-01").
        """
        if not qr_payload or not qr_payload.startswith("sb-package:"):
            return {"ok": False, "error": "invalid qr_payload"}
        try:
            package_id = int(qr_payload.split(":", 1)[1])
        except (TypeError, ValueError):
            return {"ok": False, "error": "malformed package id"}

        Package = request.env["sb.production.package"].sudo()
        package = Package.browse(package_id).exists()
        if not package:
            return {"ok": False, "error": "package not found"}

        wo = package.record_scan(workcenter_code=workcenter_code)
        # Re-read the scan log to report the running count.
        import json as _json
        try:
            log = _json.loads(package.x_scan_log_json or "[]")
        except (TypeError, ValueError):
            log = []
        return {
            "ok": True,
            "package_id": package.id,
            "wo_id": wo.id if wo else None,
            "wo_state": wo.state if wo else None,
            "scan_count": len(log),
        }
