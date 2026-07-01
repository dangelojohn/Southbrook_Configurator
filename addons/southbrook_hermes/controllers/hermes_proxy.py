# SPDX-License-Identifier: LGPL-3.0-only
"""POST /hermes/v1/ask — the browser entry point for Hermes.

Behavior is gated by the `southbrook_hermes.sidecar_enabled` system parameter:

  enabled=False (default after install):
      mints + verifies a JWT for the session and returns a JSON stub. Lets
      the OWL chat panel exercise the auth path even before a sidecar is
      deployed.

  enabled=True:
      POSTs the JWT + body to the configured `sidecar_url` and streams the
      response (text/plain) straight back to the browser.

Failures from the sidecar surface as JSON with a non-2xx status so the OWL
component can render a clear error instead of a partial answer.
"""
import json
import logging

import requests
from werkzeug.wrappers import Response

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request

from ..utils import jwt_helper

_logger = logging.getLogger(__name__)

# Stream chunk size for piping the sidecar's response to the browser.
# 4 KiB is small enough that early-emitted tokens are visible promptly.
_STREAM_CHUNK = 4096

# Cap the sidecar call so a hung upstream doesn't tie up a worker forever.
# Match Vercel's max function duration for /api/hermes/ask (60s).
_SIDECAR_TIMEOUT = 65

# Mint JWTs with enough lifetime to cover the sidecar's whole agent loop
# plus tool roundtrips. A 60s token expired mid-loop on a multi-step
# question, returned 401 to a tool call, and the model surfaced a confusing
# error to the user. 120s gives the streamText stopWhen budget headroom.
_JWT_TTL_FOR_ASK = 120


def _is_truthy(val):
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


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
                ttl_seconds=_JWT_TTL_FOR_ASK,
                extra={"order_id": body.get("order_id")})
        except RuntimeError as e:
            return self._json(
                {"error": "hermes_not_configured", "detail": str(e)},
                status=503)

        ICP = request.env["ir.config_parameter"].sudo()
        sidecar_enabled = _is_truthy(
            ICP.get_param("southbrook_hermes.sidecar_enabled"))
        sidecar_url = (ICP.get_param("southbrook_hermes.sidecar_url") or "").strip()

        if not sidecar_enabled or not sidecar_url:
            # 2026-07-01 unification — instead of echoing an empty stub,
            # route through the same `southbrook.hermes.question`
            # machinery `/my/fabio` uses. That way both Fabio surfaces
            # answer identically even before the sidecar comes online:
            # keyword-matched answers grounded in real Odoo data (MI
            # checks, production summary, user list, project state,
            # pricing help). See hermes_question.py `_answer_internal`
            # / `_answer_customer` for the keyword branches.
            user = request.env.user
            scope = "customer" if user.share else "internal"
            vals = {
                "question": (body.get("q") or "").strip(),
                "scope": scope,
                "partner_id": user.partner_id.id if scope == "customer" else False,
                "asked_by_id": user.id,
            }
            order_id = body.get("order_id")
            if order_id:
                try:
                    vals["sale_order_id"] = int(order_id)
                except (TypeError, ValueError):
                    pass
            question = request.env["southbrook.hermes.question"].sudo().create(vals)
            question.action_answer()
            return self._json({
                "stub": True,
                "answer": question.answer or "(No answer generated.)",
                "persona": persona,
                "tier": tier,
                "question_id": question.id,
            })

        # Live path — proxy to the sidecar.
        try:
            upstream = requests.post(
                f"{sidecar_url.rstrip('/')}/api/hermes/ask",
                data=json.dumps({
                    "q": body.get("q", ""),
                    "order_id": body.get("order_id"),
                }),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                stream=True,
                timeout=_SIDECAR_TIMEOUT,
            )
        except requests.RequestException as e:
            _logger.warning("Sidecar unreachable: %s", e)
            return self._json(
                {"error": "sidecar_unreachable", "detail": str(e)},
                status=502)

        if not upstream.ok:
            # Pass the error through. Try to preserve the upstream's JSON
            # error envelope; fall back to a synthesized one. Close the
            # streamed Response explicitly — otherwise the socket leaks
            # for the lifetime of the worker (generate() never runs on
            # this path, so its finally:close() never fires).
            try:
                payload = upstream.json()
            except ValueError:
                payload = {
                    "error": "sidecar_error",
                    "status": upstream.status_code,
                    "detail": upstream.text[:512],
                }
            upstream.close()
            return self._json(payload, status=upstream.status_code)

        # Stream the body straight to the browser. The OWL component reads
        # the response with `getReader()` and appends chunks to the
        # in-progress assistant message.
        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=_STREAM_CHUNK):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        mimetype = (upstream.headers.get("Content-Type") or "text/plain").split(";")[0].strip()
        return Response(
            generate(),
            mimetype=mimetype,
            headers={"Cache-Control": "no-store"},
        )

    def _json(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, default=str),
            headers=[("Content-Type", "application/json")],
            status=status,
        )
