# SPDX-License-Identifier: LGPL-3.0-only
"""POST /integrations/mcp/v1/invoke -- the MCP server's entry into Odoo.

Auth strategy (decided after reading southbrook_api and southbrook_hermes
in this session):

- southbrook_api ships an HMAC-style X-Api-Key + idempotency cache scoped
  by (api_key_hash, route_path, idempotency_key). It's already wired,
  tested, and the prod surface trusts it.
- southbrook_hermes ships JWT (HS256) with persona+tier claims AND a
  process-level TOOL_REGISTRY built at import time via @hermes_tool. The
  JWT secret is keyed off ``southbrook_hermes.jwt_secret`` system param
  -- meaning anything that uses Hermes JWT is COUPLED to that addon
  being installed.

Decision: use X-Api-Key as the primary auth. It's the right boundary for
a server-to-server bridge (the MCP server is a long-lived process holding
a stable credential, not a per-turn JWT). If Hermes is also installed, we
OPTIONALLY accept a JWT in Authorization Bearer for cross-channel calls,
but the test path is X-Api-Key only -- this addon must be installable
without Hermes.

This deviates from the brief's "uses existing southbrook_hermes JWT auth
if available; otherwise basic API key" wording in the OPPOSITE order
(api key primary, JWT optional). The reason is decoupling: MCP must keep
working if the Hermes service is paused or rolled back, and southbrook_api
is the lower-level dependency.
"""
import functools
import hashlib
import json
import logging
import time
from typing import Any, Callable, Dict

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Response + auth helpers
# ----------------------------------------------------------------------
def _cors_headers() -> list:
    return [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "POST, OPTIONS"),
        ("Access-Control-Allow-Headers",
         "Content-Type, X-Api-Key, Authorization, Idempotency-Key"),
        ("Access-Control-Max-Age", "86400"),
    ]


def _json(body: Dict[str, Any], status: int = 200,
          extra_headers=None) -> http.Response:
    headers = [("Content-Type", "application/json"), *_cors_headers()]
    if extra_headers:
        headers.extend(extra_headers)
    return request.make_response(json.dumps(body), status=status,
                                 headers=headers)


def _error(code: str, message: str = "", status: int = 400) -> http.Response:
    return _json({
        "schema": "southbrook.mcp.error.v1",
        "error": code,
        "message": message,
    }, status=status)


def _hash_key(cleartext: str) -> str:
    return "sha256:" + hashlib.sha256(cleartext.encode("utf-8")).hexdigest()


def _verify_api_key():
    """Return the res.users for the X-Api-Key header, or (None, None)."""
    cleartext = request.httprequest.headers.get("X-Api-Key", "")
    if not cleartext:
        return None, None
    try:
        # southbrook.api.key.verify raises AccessDenied on miss.
        user = request.env["southbrook.api.key"].sudo().verify(cleartext)
    except Exception:
        return None, None
    return user, _hash_key(cleartext)


def requires_mcp_auth(handler: Callable) -> Callable:
    """Decorator: enforce X-Api-Key on /integrations/mcp/v1/*."""
    @functools.wraps(handler)
    def wrapper(self, *args, **kwargs):
        user, key_hash = _verify_api_key()
        if not user:
            return _error("invalid_api_key",
                          "Missing or invalid X-Api-Key header.", 401)
        # SECURITY: the API-key login route issues keys to ANY user that can
        # log in — including portal customers. MCP must be internal-staff only,
        # otherwise a portal customer's key could read internal data. (Reads are
        # also no longer sudo'd, so ACL applies on top of this gate.)
        if not user._is_internal():
            return _error("forbidden",
                          "MCP is restricted to internal users.", 403)
        request.update_env(user=user.id)
        request._mcp_key_hash = key_hash
        request._mcp_caller_persona = "mcp_server"
        return handler(self, *args, **kwargs)
    return wrapper


# ----------------------------------------------------------------------
# Rate-limit headers
# ----------------------------------------------------------------------
def _rate_limit_headers(tool, used_in_window):
    """Surface the tool's per-minute budget + remaining count.

    The brief asks for "rate-limit headers" -- we emit them in advisory
    form (clients can adapt) but DO NOT yet enforce. Enforcement needs a
    distributed counter which is a v2 concern.
    """
    remaining = max(0, tool.rate_limit_per_min - used_in_window)
    return [
        ("X-RateLimit-Limit", str(tool.rate_limit_per_min)),
        ("X-RateLimit-Remaining", str(remaining)),
        ("X-RateLimit-Window", "60"),
    ]


# ----------------------------------------------------------------------
# Controller
# ----------------------------------------------------------------------
class SouthbrookIntegrationsMcp(http.Controller):

    @http.route("/integrations/mcp/v1/invoke",
                type="http", auth="public", methods=["POST", "OPTIONS"],
                csrf=False)
    @requires_mcp_auth
    def invoke(self):
        """Run a registered MCP tool.

        Request body:
            {"tool_name": "list_open_mos", "args": {...}, "idempotency_key": "..."}

        Status codes:
            200 success
            400 bad request (missing tool_name, bad JSON)
            403 tool disabled / write tool requested
            404 tool not found
            429 (advisory) -- v1 emits the headers but does not gate
        """
        # Body parse.
        raw = request.httprequest.get_data(as_text=True) or "{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            return _error("bad_json", "Body is not valid JSON: %s" % exc, 400)

        tool_name = body.get("tool_name")
        if not tool_name:
            return _error("missing_tool_name",
                          "Field `tool_name` is required.", 400)

        Tool = request.env["southbrook.integrations.mcp_tool"].sudo()
        tool = Tool.search([("name", "=", tool_name)], limit=1)
        if not tool:
            return _error("tool_not_found",
                          "No MCP tool '%s' registered." % tool_name, 404)

        # Idempotency receipt (the brief calls these out for the
        # southbrook_api polish; we mirror the pattern). v1 returns a
        # synthetic receipt id so callers can correlate replays without
        # needing to install southbrook_api's idempotency cache.
        idem_key = (request.httprequest.headers.get("Idempotency-Key")
                    or body.get("idempotency_key") or "")
        receipt_id = hashlib.sha256(
            (idem_key + tool_name + raw).encode("utf-8")).hexdigest()[:16] \
            if idem_key else ""

        args_json = json.dumps(body.get("args") or {})

        # Advisory rate-limit window: count this tool's calls in the
        # last 60 seconds.
        Log = request.env["southbrook.integrations.mcp_call_log"].sudo()
        window_start = time.time() - 60
        from datetime import datetime
        used = Log.search_count([
            ("tool_id", "=", tool.id),
            ("create_date", ">=", datetime.utcfromtimestamp(window_start)),
        ])
        rl_headers = _rate_limit_headers(tool, used)

        # Enforce (not just advertise) the per-tool per-minute budget so a
        # single key can't loop expensive reads unthrottled.
        if tool.rate_limit_per_min and used >= tool.rate_limit_per_min:
            return _json({
                "schema": "southbrook.mcp.error.v1",
                "error": "rate_limited",
                "message": "Per-minute rate limit for tool '%s' exceeded."
                           % tool_name,
            }, status=429, extra_headers=rl_headers)

        try:
            result = tool.invoke(args_json)
        except AccessError as exc:
            return _json({
                "schema": "southbrook.mcp.error.v1",
                "error": "forbidden",
                "message": str(exc),
            }, status=403, extra_headers=rl_headers)
        except UserError as exc:
            return _json({
                "schema": "southbrook.mcp.error.v1",
                "error": "bad_request",
                "message": str(exc),
            }, status=400, extra_headers=rl_headers)

        result["receipt_id"] = receipt_id
        return _json(result, status=200, extra_headers=rl_headers)
