# SPDX-License-Identifier: LGPL-3.0-only
"""POST /hermes/v1/ask — the browser entry point for Hermes.

B1 stubs the downstream sidecar call: it mints a JWT and returns a stub
response so the auth + persona-resolution path is exercised end-to-end.
B2 (Vercel sidecar) replaces the stub with a streaming POST to the sidecar
and pipes the SSE response back to the browser.
"""
import json
import logging

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request

from ..utils import jwt_helper

_logger = logging.getLogger(__name__)


class HermesProxyController(http.Controller):

    @http.route("/hermes/v1/ask", type="http", auth="user",
                methods=["POST"], csrf=False)
    def ask(self, **kw):
        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid_json"}, status=400)

        try:
            persona = jwt_helper.resolve_persona(request.env.user)
        except AccessError as e:
            return self._json(
                {"error": "forbidden", "detail": str(e)}, status=403)
        except RuntimeError as e:
            return self._json(
                {"error": "hermes_not_configured", "detail": str(e)},
                status=503)

        tier = jwt_helper.tier_for_persona(persona)
        partner_id = request.env.user.partner_id.id
        try:
            token = jwt_helper.mint_jwt(
                request.env, tenant="southbrook", persona=persona,
                partner_id=partner_id, tier=tier,
                extra={"order_id": body.get("order_id")})
        except RuntimeError as e:
            return self._json(
                {"error": "hermes_not_configured", "detail": str(e)},
                status=503)

        # B1: stub the downstream call. B2 will POST `token + body` to the
        # sidecar (env: southbrook_hermes.sidecar_url) and stream the
        # response back via SSE.
        claims = jwt_helper.verify_jwt(request.env, token)
        stub_answer = (
            f"(Stub answer — sidecar not yet wired.) Question received: "
            f"'{body.get('q', '')}'.")
        return self._json({
            "stub": True,
            "answer": stub_answer,
            "persona": persona,
            "tier": tier,
            "jwt_iat_seen": claims["iat"],
        })

    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, default=str),
            headers=[("Content-Type", "application/json")],
            status=status,
        )
