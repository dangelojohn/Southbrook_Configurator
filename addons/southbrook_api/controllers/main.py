# SPDX-License-Identifier: LGPL-3.0-only
"""/api/v1/* surface — G6 reference implementation.

Every response carries `schema: 'southbrook.flutter.api.v1'`.
Error responses follow the G6 §4 envelope with stable `error` codes.
"""
import functools
import hashlib
import json
import logging
from typing import Any, Callable, Dict, Optional

from odoo import _, http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

SCHEMA_VERSION = "southbrook.flutter.api.v1"


# ----------------------------------------------------------------------
# Response helpers
# ----------------------------------------------------------------------
def _json(body: Dict[str, Any], status: int = 200) -> http.Response:
    body.setdefault("schema", SCHEMA_VERSION)
    payload = json.dumps(body)
    return request.make_response(
        payload, status=status,
        headers=[("Content-Type", "application/json")],
    )


def _error(code: str, message: str = "", status: int = 400,
           details: Optional[dict] = None) -> http.Response:
    body: Dict[str, Any] = {"error": code, "message": message or code}
    if details:
        body["details"] = details
    return _json(body, status=status)


def _hash_key(cleartext: str) -> str:
    return "sha256:" + hashlib.sha256(cleartext.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# Auth + idempotency decorators
# ----------------------------------------------------------------------
def _verify_request_key():
    """Return (user, api_key_hash) for the X-Api-Key header, or send
    a 401 response back to the caller."""
    cleartext = request.httprequest.headers.get("X-Api-Key", "")
    if not cleartext:
        return None, None
    try:
        user = request.env["southbrook.api.key"].sudo().verify(cleartext)
    except AccessDenied as exc:
        return None, None
    return user, _hash_key(cleartext)


def requires_api_key(handler: Callable) -> Callable:
    """Decorator: enforce X-Api-Key on a controller route."""
    @functools.wraps(handler)
    def wrapper(self, *args, **kwargs):
        user, api_key_hash = _verify_request_key()
        if not user:
            return _error("invalid_api_key",
                          "Missing or invalid X-Api-Key header.", 401)
        # Sudo into the API user's environment (mirrors session auth).
        request.update_env(user=user.id)
        request._api_key_hash = api_key_hash
        return handler(self, *args, **kwargs)
    return wrapper


def supports_idempotency(handler: Callable) -> Callable:
    """Decorator: replay cached response on Idempotency-Key hit."""
    @functools.wraps(handler)
    def wrapper(self, *args, **kwargs):
        idempotency_key = request.httprequest.headers.get(
            "Idempotency-Key", "")
        api_key_hash = getattr(request, "_api_key_hash", "")
        Cache = request.env["southbrook.api.idempotency"].sudo()
        if idempotency_key:
            hit = Cache.get_cached(api_key_hash, idempotency_key)
            if hit is not None:
                status_code, body = hit
                return request.make_response(
                    body, status=status_code,
                    headers=[("Content-Type", "application/json")],
                )
        resp = handler(self, *args, **kwargs)
        if idempotency_key and 200 <= getattr(resp, "status_code", 0) < 300:
            try:
                Cache.stash(api_key_hash, idempotency_key,
                            resp.status_code, resp.get_data(as_text=True))
            except Exception:
                _logger.debug("idempotency stash failed", exc_info=True)
        return resp
    return wrapper


# ----------------------------------------------------------------------
# Controller
# ----------------------------------------------------------------------
class SouthbrookApi(http.Controller):

    # ==================================================================
    # §3.1 — POST /api/v1/auth/login
    # ==================================================================
    @http.route(
        "/api/v1/auth/login", type="http", auth="public",
        methods=["POST"], csrf=False,
    )
    def auth_login(self, **_):
        try:
            payload = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            return _error("bad_json", "Request body is not JSON.", 400)
        email = (payload.get("email") or "").strip().lower()
        password = payload.get("password") or ""
        if not (email and password):
            return _error("missing_credentials", "email + password required", 400)

        # Resolve email → res.users.
        user = request.env["res.users"].sudo().search(
            [("login", "=", email)], limit=1,
        )
        if not user:
            return _error("invalid_credentials", "Login failed.", 401)
        # Authenticate via the standard hook (handles 2FA hooks, lockouts, etc).
        try:
            request.env["res.users"].sudo().with_context(active_test=False)\
                ._login({"login": email, "type": "password",
                          "password": password},
                         {"interactive": False})
        except AccessDenied:
            return _error("invalid_credentials", "Login failed.", 401)

        issued = request.env["southbrook.api.key"].sudo().issue_for_user(
            user, label="api_login",
        )
        return _json({
            "api_key": issued["cleartext"],
            "expires_at": (issued["expires_at"] and
                           issued["expires_at"].isoformat() + "Z"),
            "user": {"id": user.id, "name": user.name, "email": user.login},
        })

    # ==================================================================
    # §3.1 — GET /api/v1/me
    # ==================================================================
    @http.route(
        "/api/v1/me", type="http", auth="public",
        methods=["GET"], csrf=False,
    )
    @requires_api_key
    def me(self, **_):
        user = request.env.user
        partner = user.partner_id
        is_dealer = (
            hasattr(partner, "channel") and partner.channel == "dealer"
        )
        return _json({
            "user": {
                "id": user.id, "name": user.name, "email": user.login,
                "is_dealer": is_dealer,
                "currency": (
                    request.env.company.currency_id.name if request.env.company else None
                ),
            },
        })

    # ==================================================================
    # §3.2 — GET /api/v1/kitchen-projects
    # ==================================================================
    @http.route(
        "/api/v1/kitchen-projects", type="http", auth="public",
        methods=["GET"], csrf=False,
    )
    @requires_api_key
    def list_projects(self, **_):
        Project = request.env["sb.kitchen.project"].sudo()
        partner = request.env.user.partner_id
        projects = Project.search(
            [("partner_id", "=", partner.id)],
            order="date_created desc",
        )
        return _json({
            "projects": [self._project_summary(p) for p in projects],
            "next_cursor": None,
        })

    # ==================================================================
    # §3.3 — GET /api/v1/kitchen-projects/<id>
    # ==================================================================
    @http.route(
        "/api/v1/kitchen-projects/<int:project_id>",
        type="http", auth="public", methods=["GET"], csrf=False,
    )
    @requires_api_key
    def project_detail(self, project_id, **_):
        project = self._fetch_project_or_404(project_id)
        if isinstance(project, http.Response):
            return project
        return _json({"project": self._project_detail(project)})

    # ==================================================================
    # §3.4 — POST /api/v1/kitchen-projects/<id>/photos (multipart)
    # ==================================================================
    @http.route(
        "/api/v1/kitchen-projects/<int:project_id>/photos",
        type="http", auth="public", methods=["POST"], csrf=False,
    )
    @requires_api_key
    @supports_idempotency
    def upload_photo(self, project_id, **post):
        project = self._fetch_project_or_404(project_id)
        if isinstance(project, http.Response):
            return project

        file_storage = request.httprequest.files.get("photo")
        if not file_storage:
            return _error("missing_photo", "Multipart field 'photo' missing.", 400)
        # Size cap (7 MB per G6 §3.4).
        data = file_storage.read()
        if len(data) > 7 * 1024 * 1024:
            return _error("payload_too_large",
                          "Photo exceeds 7 MB.", 413)
        ctype = (file_storage.mimetype or "").lower()
        if ctype not in ("image/jpeg", "image/jpg", "image/png"):
            return _error("unsupported_media_type",
                          f"Unsupported mime type {ctype!r}.", 415)

        attachment = request.env["ir.attachment"].sudo().create({
            "name": file_storage.filename or "photo.jpg",
            "raw": data,
            "res_model": "sb.kitchen.project",
            "res_id": project.id,
            "mimetype": ctype,
        })

        prompt_code = (post.get("prompt_template_code") or "default_v1").strip()
        try:
            analysis = project.sudo().analyze_photo(
                attachment.id, prompt_template_code=prompt_code,
            )
        except UserError as exc:
            return _error("analyze_failed", str(exc.args and exc.args[0] or exc), 502)

        return _json({
            "attachment_id": attachment.id,
            "analysis_id": analysis.id,
            "appliance_count": len(project.appliance_ids),
            "warnings": [],
        })

    # ==================================================================
    # §3.5 — GET /api/v1/kitchen-projects/<id>/concepts
    # ==================================================================
    @http.route(
        "/api/v1/kitchen-projects/<int:project_id>/concepts",
        type="http", auth="public", methods=["GET"], csrf=False,
    )
    @requires_api_key
    def list_concepts(self, project_id, **_):
        project = self._fetch_project_or_404(project_id)
        if isinstance(project, http.Response):
            return project
        return _json({
            "concepts": [self._concept_dict(o) for o in project.design_option_ids],
        })

    # ==================================================================
    # §3.6 — POST /api/v1/kitchen-projects/<id>/concepts/<opt_id>/select
    # ==================================================================
    @http.route(
        "/api/v1/kitchen-projects/<int:project_id>/concepts/<int:option_id>/select",
        type="http", auth="public", methods=["POST"], csrf=False,
    )
    @requires_api_key
    @supports_idempotency
    def select_concept(self, project_id, option_id, **_):
        project = self._fetch_project_or_404(project_id)
        if isinstance(project, http.Response):
            return project
        option = project.design_option_ids.filtered(lambda o: o.id == option_id)
        if not option:
            return _error("option_not_in_project",
                          "That design option does not belong to this project.", 404)
        option.sudo().write({"is_selected": True})
        return _json({"ok": True, "selected_id": option.id})

    # ==================================================================
    # §3.7 — POST /api/v1/kitchen-projects/<id>/approve
    # ==================================================================
    @http.route(
        "/api/v1/kitchen-projects/<int:project_id>/approve",
        type="http", auth="public", methods=["POST"], csrf=False,
    )
    @requires_api_key
    @supports_idempotency
    def approve(self, project_id, **_):
        project = self._fetch_project_or_404(project_id)
        if isinstance(project, http.Response):
            return project

        if not project.selected_design_option_id:
            return _error("no_concept_selected",
                          "Select a concept before approving.", 409)
        if project.state != "awaiting_customer":
            return _error("invalid_state",
                          f"project.state={project.state}", 409)

        try:
            body = json.loads(request.httprequest.data or b"{}")
        except json.JSONDecodeError:
            body = {}
        notes = body.get("notes") or ""

        approval = request.env["sb.kitchen.approval"].sudo().create({
            "project_id": project.id,
            "approval_type": "design",
            "approver_id": request.env.user.id,
            "approver_type": "customer",
            "state": "approved",
            "notes": notes,
        })
        project.sudo().action_customer_approves()
        return _json({
            "ok": True,
            "approval_id": approval.id,
            "project_state": project.state,
        })

    # ==================================================================
    # Helpers
    # ==================================================================
    def _fetch_project_or_404(self, project_id):
        """Return the project IF the current API user owns it, else
        an error response. Mirrors the customer-portal pattern so we
        do not leak existence of other customers' projects."""
        Project = request.env["sb.kitchen.project"].sudo()
        project = Project.browse(project_id).exists()
        if not project:
            return _error("project_not_found", "Project not found.", 404)
        partner = request.env.user.partner_id
        if project.partner_id != partner:
            _logger.warning(
                "API ACL: user %s (partner %s) attempted to access "
                "project %s owned by partner %s — denied.",
                request.env.user.id, partner.id, project.id,
                project.partner_id.id,
            )
            return _error("project_not_found", "Project not found.", 404)
        return project

    def _project_summary(self, p):
        return {
            "id": p.id, "code": p.code, "name": p.name,
            "state": p.state, "theme": p.theme,
            "date_target": p.date_target and p.date_target.isoformat(),
            "cover_attachment_id": None,
            "concept_count": len(p.design_option_ids),
            "has_unread_messages": False,
        }

    def _project_detail(self, p):
        return {
            "id": p.id, "code": p.code, "name": p.name,
            "state": p.state, "theme": p.theme,
            "salesperson": {
                "id": p.salesperson_id.id,
                "name": p.salesperson_id.name,
                "email": p.salesperson_id.login,
            } if p.salesperson_id else None,
            "ai_ready": p.is_ready_for_config_engine(),
            "selected_design_option_id": p.selected_design_option_id.id or None,
            "photo_attachment_ids": [],
            "concept_ids": p.design_option_ids.ids,
            "approval_history": [
                {"id": a.id, "type": a.approval_type, "state": a.state,
                 "date": a.date_decided and a.date_decided.isoformat() or None}
                for a in p.approval_ids
            ],
        }

    def _concept_dict(self, opt):
        try:
            placement = json.loads(opt.placement_data_json or "null")
        except json.JSONDecodeError:
            placement = None
        return {
            "id": opt.id, "name": opt.name,
            "description_html": opt.description or "",
            "estimated_price": opt.estimated_price,
            "estimated_lead_time_days": opt.estimated_lead_time_days,
            "preview_attachment_id": opt.preview_attachment_id.id or None,
            "is_selected": opt.is_selected,
            "placement_data": placement,
        }
