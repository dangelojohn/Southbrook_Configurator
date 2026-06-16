# SPDX-License-Identifier: LGPL-3.0-only
"""GET /api/hermes/tools + POST /api/hermes/tools/<slug>.

The Hermes sidecar fetches the registry once at startup and dispatches
individual tool calls back through this controller. Every call is JWT-bearer
authenticated; the JWT's `persona` + `tier` claims gate which tools the
caller can see and call.
"""
import json
import logging

from odoo import http
from odoo.http import request

from ..tools import decorator
from ..utils import jwt_helper

_logger = logging.getLogger(__name__)


class HermesToolsApiController(http.Controller):

    @http.route("/api/hermes/tools", type="http", auth="public",
                methods=["GET"], csrf=False)
    def registry(self, **kw):
        claims = self._verify()
        if isinstance(claims, http.Response):
            return claims
        tools = decorator.registry_for_persona(
            claims["persona"], claims["tier"])
        return self._json({
            "tenant": claims["tenant"],
            "persona": claims["persona"],
            "tier": claims["tier"],
            "tools": tools,
        })

    @http.route("/api/hermes/tools/<slug>", type="http", auth="public",
                methods=["POST"], csrf=False)
    def dispatch(self, slug, **kw):
        claims = self._verify()
        if isinstance(claims, http.Response):
            return claims
        fn = decorator.get_tool_function(slug)
        if fn is None:
            return self._json({"error": "unknown_tool", "slug": slug}, status=404)
        meta = next(
            (t for t in decorator.TOOL_REGISTRY if t["slug"] == slug), None)
        if claims["persona"] not in meta["personas"]:
            return self._json(
                {"error": "not_allowed_for_persona", "persona": claims["persona"]},
                status=403)
        allowed_tiers = set(claims["tier"].split("+"))
        if meta["tier"] not in allowed_tiers:
            return self._json(
                {"error": "tier_required", "required_tier": meta["tier"]},
                status=403)
        try:
            args = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid_json"}, status=400)
        # Look up the partner's user record for record-rule scoping.
        partner = request.env["res.partner"].sudo().browse(claims["partner_id"])
        user = partner.user_ids[:1] or request.env.user
        env_with_user = request.env(user=user.id)
        try:
            result = fn(env_with_user, **args)
        except Exception as e:
            _logger.exception("Tool %s raised", slug)
            return self._json(
                {"error": "tool_exception", "detail": str(e), "tool": slug},
                status=500)
        return self._json(result)

    def _verify(self):
        auth = request.httprequest.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return self._json(
                {"error": "missing_bearer_token"}, status=401)
        token = auth[len("Bearer "):].strip()
        try:
            return jwt_helper.verify_jwt(request.env, token)
        except RuntimeError as e:
            return self._json(
                {"error": "hermes_not_configured", "detail": str(e)},
                status=503)
        except Exception as e:
            return self._json(
                {"error": "invalid_token", "detail": str(e)}, status=401)

    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, default=str),
            headers=[("Content-Type", "application/json")],
            status=status,
        )
