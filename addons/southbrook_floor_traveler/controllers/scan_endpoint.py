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
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def floor_traveler_scan(self, qr_payload=None, workcenter_code=None, **kw):
        """Receive a scan event from the shop floor.

        :param qr_payload: the QR's decoded text. Accepts BOTH formats:
            - Legacy:  "sb-package:<id>"  (pre-qr_kit, all current
              floor_traveler PDFs use this)
            - qr_kit:  "sb://pkg/<id>?t=<ts>&s=<hmac>"  (signed
              payload for the unified /sb/qr/scan controller; lets
              external scanners that already speak qr_kit's wire
              format hit this endpoint without an upgrade)
        :param workcenter_code: free-text identifier of the scanning
            station (e.g. "PANEL-SAW-01").

        Unified audit (added 2026-06-26): every scan now ALSO writes
        to southbrook.qr.scan.log (when qr_kit is installed) so the
        legacy + qr_kit scan paths feed one search/group/dashboard
        instead of two.
        """
        env = request.env
        # SECURITY: the endpoint sudo-advances a workorder (button_finish +
        # tool-consumption debit) for a client-supplied package id. auth="user"
        # admits ANY session — a shop-floor operator, but ALSO an external
        # portal dealer/customer — so without this gate any authenticated caller
        # could finish production for any job by guessing a package id (the
        # legacy sb-package:<id> format is unsigned). Shop-floor scanning is a
        # GROUP-authorized action (any mrp operator, any job at their station);
        # require an internal mrp user.
        caller = env.user
        if not caller._is_internal() \
                or not caller.has_group("mrp.group_mrp_user"):
            self._log_unified(env, qr_payload, "access_denied",
                              error="caller not an internal mrp operator",
                              workcenter_code=workcenter_code)
            return {"ok": False, "error": "forbidden"}
        if not qr_payload:
            self._log_unified(env, qr_payload, "error",
                              error="empty qr_payload",
                              workcenter_code=workcenter_code)
            return {"ok": False, "error": "empty qr_payload"}

        package_id = self._resolve_package_id(env, qr_payload)
        if package_id is None:
            self._log_unified(env, qr_payload, "error",
                              error="unrecognized payload format",
                              workcenter_code=workcenter_code)
            return {"ok": False, "error":
                    "invalid qr_payload (need 'sb-package:<id>' or "
                    "signed 'sb://pkg/<id>')"}

        Package = env["sb.production.package"].sudo()
        package = Package.browse(package_id).exists()
        if not package:
            self._log_unified(env, qr_payload, "record_not_found",
                              kind="pkg", ident=str(package_id),
                              error=f"package id={package_id} not found",
                              workcenter_code=workcenter_code)
            return {"ok": False, "error": "package not found"}

        wo = package.record_scan(workcenter_code=workcenter_code)
        # Re-read the scan log to report the running count.
        import json as _json
        try:
            log = _json.loads(package.x_scan_log_json or "[]")
        except (TypeError, ValueError):
            log = []

        # Unified audit trail (additive — does not replace the
        # package's per-record x_scan_log_json which the existing
        # MO/WO dashboards consume).
        self._log_unified(env, qr_payload, "ok", kind="pkg",
                          ident=str(package.id),
                          target_model="sb.production.package",
                          target_id=package.id,
                          workcenter_code=workcenter_code)
        return {
            "ok": True,
            "package_id": package.id,
            "wo_id": wo.id if wo else None,
            "wo_state": wo.state if wo else None,
            "scan_count": len(log),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _resolve_package_id(self, env, qr_payload):
        """Accept either legacy 'sb-package:<id>' or qr_kit
        'sb://pkg/<id>?...'. Return int id or None."""
        if qr_payload.startswith("sb-package:"):
            try:
                return int(qr_payload.split(":", 1)[1])
            except (TypeError, ValueError):
                return None
        if qr_payload.startswith("sb://"):
            Payload = env.get("southbrook.qr.payload")
            if not Payload:
                return None  # qr_kit not installed
            try:
                parsed = Payload.sudo().parse(qr_payload)
                # Require valid signature AND kind=='pkg' for unified
                # path. Forged or wrong-kind QRs return None.
                if (parsed.get("kind") == "pkg"
                        and parsed.get("valid_signature")):
                    return int(parsed["ident"])
            except Exception:  # noqa: BLE001
                return None
        return None

    def _log_unified(self, env, qr_payload, result, kind="",
                     ident="", target_model="", target_id=0,
                     error="", workcenter_code=""):
        """Best-effort write to southbrook.qr.scan.log. Wrapped in
        try/except so the legacy scan endpoint NEVER fails because
        the qr_kit log model is missing/unavailable."""
        try:
            if "southbrook.qr.scan.log" not in env:
                return
            env["southbrook.qr.scan.log"].sudo().create({
                # Record the REAL caller — the create runs sudo (so create_uid
                # would be OdooBot), which destroys attribution on a production-
                # mutation audit log.
                "user_id": env.uid,
                "kind": kind,
                "ident": ident,
                "action": "scan",  # legacy endpoint is always "scan"
                "result": result,
                "target_model": target_model,
                "target_id": target_id,
                "error_message": error[:255] if error else "",
                "payload": (qr_payload or "")[:500],
                "source_ip": request.httprequest.remote_addr,
                "user_agent":
                    (request.httprequest.headers.get("User-Agent") or "")[:255],
            })
        except Exception:  # noqa: BLE001
            _logger.warning(
                "floor-traveler scan: unified log write failed (non-fatal)")
