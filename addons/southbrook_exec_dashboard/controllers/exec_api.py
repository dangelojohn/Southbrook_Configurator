# SPDX-License-Identifier: LGPL-3.0-only
"""Executive Dashboard JSON endpoint.

Returns a compact morning-briefing payload for mobile clients and the
in-backend OWL component. Auth: portal session OR ``southbrook_api`` API key
header (X-Api-Key) if that addon's helper is available.
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ExecDashboardAPI(http.Controller):

    @http.route(
        "/exec/morning",
        type="http",
        auth="public",
        methods=["POST", "GET"],
        csrf=False,
    )
    def exec_morning(self, **kwargs):
        """Return the latest snapshot's KPI payload as JSON."""
        env = request.env
        uid = self._authenticate()
        if not uid:
            return self._json_response({"error": "unauthorized"}, status=401)

        # SECURITY: the payload is company-wide REVENUE / CASH / margin computed
        # under sudo below. auth="public" + a bare session check let ANY logged-in
        # user — a shop-floor operator, or a portal dealer/customer — read the
        # CFO's numbers. Gate to internal executive-group members before the
        # sudo compute; the sudo bypasses the model ACL, so this is the only
        # boundary.
        caller = env["res.users"].sudo().browse(uid)
        exec_group = "southbrook_exec_dashboard.group_southbrook_exec_dashboard_user"
        if not caller.exists() or not caller._is_internal() \
                or not caller.has_group(exec_group):
            return self._json_response({"error": "forbidden"}, status=403)

        try:
            Snapshot = env["southbrook.exec_dashboard.snapshot"].sudo()
            sid = Snapshot.get_or_create_today()
            snapshot = Snapshot.browse(sid)
            payload = snapshot._compute_kpi_payload()
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("exec/morning failed: %s", exc)
            return self._json_response({"error": "server_error"}, status=500)

        body = {
            "as_of": snapshot.as_of.isoformat() if snapshot.as_of else None,
            "units_yesterday": payload["yesterday_units_produced"],
            "fpy_7d": payload["fpy_pct_7d"],
            "otd_30d": payload["otd_pct_30d"],
            "wip": payload["wip_value_current"],
            "bottleneck": {
                "workcenter": payload["top_bottleneck_workcenter"],
                "load_pct": payload["top_bottleneck_load_pct"],
            },
            "revenue_30d": payload["revenue_last_30d"],
            "cash": payload["cash_position"],
        }
        return self._json_response(body, status=200)

    # ---- helpers ----
    def _authenticate(self):
        """Return a uid if the caller has a valid portal session OR a valid
        southbrook_api X-Api-Key. Otherwise return None."""
        env = request.env
        if request.session and request.session.uid:
            return request.session.uid

        api_key = request.httprequest.headers.get("X-Api-Key")
        if api_key:
            ApiKey = env.get("southbrook.api.key")
            if ApiKey is not None:
                # Use the model's timing-safe verify() — the key is stored
                # HASHED (key_hash), there is no cleartext `key` field, so the
                # old search([("key","=",api_key)]) referenced a non-existent
                # field (runtime error) and bypassed the hash comparison.
                try:
                    user = ApiKey.sudo().verify(api_key)
                except Exception:
                    user = None
                if user:
                    return user.id
            # Fall back to res.users.api.keys if southbrook_api isn't installed
            CoreKeys = env.get("res.users.apikeys")
            if CoreKeys is not None:
                user_id = CoreKeys.sudo()._check_credentials(
                    scope="rpc", key=api_key
                ) if hasattr(CoreKeys, "_check_credentials") else None
                if user_id:
                    return user_id
        return None

    def _json_response(self, body, status=200):
        response = request.make_response(
            json.dumps(body, default=str),
            headers=[
                ("Content-Type", "application/json"),
                ("Cache-Control", "no-store"),
            ],
        )
        response.status_code = status
        return response
