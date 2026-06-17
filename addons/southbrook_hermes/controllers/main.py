# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.southbrook_api.controllers.main import (
    _cors_preflight,
    _error,
    _json,
    requires_api_key,
)


class SouthbrookHermesApi(http.Controller):

    @http.route(
        "/hermes/api/v1/recommendations", type="http", auth="public",
        methods=["OPTIONS"], csrf=False,
    )
    def recommendations_preflight(self, **_):
        return _cors_preflight()

    @http.route(
        "/hermes/api/v1/recommendations", type="http", auth="public",
        methods=["POST"], csrf=False,
    )
    @requires_api_key
    def create_recommendation(self, **_):
        try:
            payload = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return _error("bad_json", "Request body is not JSON.", 400)
        if not isinstance(payload, dict):
            return _error("bad_json", "Request body must be a JSON object.", 400)

        name = (payload.get("name") or "").strip()
        summary = (payload.get("summary") or "").strip()
        if not name or not summary:
            return _error("missing_fields", "name and summary are required.", 400)

        raw_payload = payload.get("payload", {})
        if raw_payload is None:
            raw_payload = {}
        if not isinstance(raw_payload, dict):
            return _error("bad_payload", "payload must be a JSON object.", 400)

        values = {
            "name": name,
            "summary": summary,
            "recommendation_type": payload.get("recommendation_type") or "task",
            "priority": payload.get("priority") or "normal",
            "rationale": payload.get("rationale") or False,
            "proposed_action": payload.get("proposed_action") or False,
            "source_model": payload.get("source_model") or False,
            "source_res_id": int(payload.get("source_res_id") or 0),
            "payload_json": json.dumps(raw_payload, sort_keys=True),
            "agent_run_id": payload.get("agent_run_id") or False,
            "model_provider": payload.get("model_provider") or False,
            "model_name": payload.get("model_name") or False,
        }
        try:
            rec = request.env["southbrook.hermes.recommendation"].sudo().create(values)
        except (UserError, ValidationError, ValueError) as exc:
            return _error("validation_error", str(exc), 400)

        # Optional fast-path: when the caller has already gone through human
        # approval on its own side (e.g. the external Hermes Console UI
        # approved a prospect_lead via WhatsApp or the web UI) it can pass
        # ``auto_apply: true`` to skip the redundant in-Odoo approval gate.
        #
        # Limited to recommendation_type='prospect' for now — generic tasks
        # MUST still flow through the human-approval boundary that the
        # Fabio addon is designed around. Prospects are a self-contained
        # safe action (creating a crm.lead is reversible and audit-trailed)
        # so single-stage approval is fine.
        auto_apply = bool(payload.get("auto_apply"))
        if auto_apply and rec.recommendation_type == "prospect":
            try:
                rec.action_mark_ready()
                rec.action_approve()
                rec.action_apply()
            except (UserError, ValidationError) as exc:
                # Recommendation was created; the auto-apply failed. Return
                # the partial success rather than rolling back so the caller
                # can see the rec in Odoo and apply manually.
                return _json({
                    "ok": True,
                    "recommendation_id": rec.id,
                    "state": rec.state,
                    "auto_apply_error": str(exc),
                })

        return _json({
            "ok": True,
            "recommendation_id": rec.id,
            "state": rec.state,
            "created_crm_lead_id": (
                rec.created_crm_lead_id.id if rec.created_crm_lead_id else None
            ),
        })
