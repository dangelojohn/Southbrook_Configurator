# SPDX-License-Identifier: LGPL-3.0-only
"""HTTP controller for the FreeCAD-bridge callback.

POST /plm/cad_callback
  Body (JSON):
    {
      "job_id":        <bridge job id, opaque string>,
      "production_id": <int, mrp.production.id>,
      "status":        "done" | "error",
      "error":         <optional str if status == error>,
      "attachment_ids": [<int>, ...]   # ir.attachment ids the bridge
                                       # already wrote via XML-RPC.
    }
  Headers:
    X-Bridge-Secret: <shared secret from FREECAD_BRIDGE_SECRET env var>

Auth: the controller compares the X-Bridge-Secret header against the
ir.config_parameter `freecad_bridge.secret`. No secret configured → 503.
Mismatch → 401.

The bridge already attached the rendered files as ir.attachment records
before calling back, so this endpoint just links them to the MO and
flips x_cad_status. (Decoupled to keep the callback idempotent — repeat
calls converge on the same state.)

G2a note: this controller is INERT until the owner gives Module 2
deployment go-ahead. Until then, the server action that POSTs jobs to
the bridge is not registered, so no callback can fire in production.
The controller body is here so the test suite can exercise it without
the server action.
"""
import json
import logging

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request

_logger = logging.getLogger(__name__)


class FreecadBridgeController(http.Controller):

    @http.route(
        "/plm/cad_callback",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def cad_callback(self, **_):
        # ---- Shared-secret auth ----
        param = request.env["ir.config_parameter"].sudo()
        configured = param.get_param("freecad_bridge.secret")
        if not configured:
            _logger.warning("cad_callback rejected: bridge secret not configured")
            return request.make_response(
                json.dumps({"error": "bridge_secret_unset"}),
                status=503,
                headers=[("Content-Type", "application/json")],
            )
        provided = request.httprequest.headers.get("X-Bridge-Secret", "")
        if provided != configured:
            _logger.warning("cad_callback rejected: bad X-Bridge-Secret header")
            raise AccessError("Invalid bridge secret")

        # ---- Body parse ----
        try:
            payload = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return request.make_response(
                json.dumps({"error": "bad_json"}),
                status=400,
                headers=[("Content-Type", "application/json")],
            )

        production_id = payload.get("production_id")
        status = payload.get("status")
        attachment_ids = payload.get("attachment_ids") or []

        if not production_id or status not in ("done", "error"):
            return request.make_response(
                json.dumps({"error": "missing_or_invalid_fields"}),
                status=400,
                headers=[("Content-Type", "application/json")],
            )

        Production = request.env["mrp.production"].sudo()
        mo = Production.browse(int(production_id)).exists()
        if not mo:
            return request.make_response(
                json.dumps({"error": "unknown_production"}),
                status=404,
                headers=[("Content-Type", "application/json")],
            )

        values = {"x_cad_status": status}
        if attachment_ids:
            values["x_cad_attachment_ids"] = [(6, 0, [int(a) for a in attachment_ids])]
        mo.write(values)

        _logger.info(
            "cad_callback applied: mo=%s status=%s attachments=%s",
            mo.id, status, len(attachment_ids),
        )
        return request.make_response(
            json.dumps({"ok": True, "production_id": mo.id, "status": status}),
            status=200,
            headers=[("Content-Type", "application/json")],
        )
