# SPDX-License-Identifier: LGPL-3.0-only
"""POST /api/hermes/conversation/log — sidecar persists Q+A turns."""
import json

from odoo import http
from odoo.http import request

from ..utils import jwt_helper


class HermesConversationApiController(http.Controller):

    @http.route("/api/hermes/conversation/log", type="http", auth="public",
                methods=["POST"], csrf=False)
    def log(self, **kw):
        auth = request.httprequest.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return self._json(
                {"error": "missing_bearer_token"}, status=401)
        try:
            claims = jwt_helper.verify_jwt(
                request.env, auth[len("Bearer "):].strip())
        except RuntimeError as e:
            return self._json(
                {"error": "hermes_not_configured", "detail": str(e)},
                status=503)
        except Exception as e:
            return self._json(
                {"error": "invalid_token", "detail": str(e)}, status=401)
        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid_json"}, status=400)
        Q = request.env["southbrook.hermes.question"].sudo()
        rec = Q.log_conversation(
            question=body.get("question", ""),
            answer=body.get("answer", ""),
            partner_id=claims["partner_id"],
            scope=body.get("scope", "customer"),
            project_id=body.get("project_id"),
            order_id=body.get("order_id"),
        )
        return self._json({"ok": True, "question_id": rec.id})

    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, default=str),
            headers=[("Content-Type", "application/json")],
            status=status,
        )
