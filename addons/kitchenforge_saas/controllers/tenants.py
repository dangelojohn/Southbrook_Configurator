# SPDX-License-Identifier: LGPL-3.0-only
"""/saas/v1/tenants REST surface.

Control-plane API for provisioning + lifecycle of cabinet-shop tenants.
Auth reuses the southbrook_api `X-Api-Key` decorator; in practice the
operator restricts these routes to superuser-owned keys via the standard
group ACLs (group_kitchenforge_saas_operator).
"""
import json
import logging

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.southbrook_api.controllers.main import (
    requires_api_key, supports_idempotency, _json, _error, SCHEMA_VERSION,
)

_logger = logging.getLogger(__name__)


def _tenant_to_dict(t):
    return {
        "id": t.id,
        "name": t.name,
        "slug": t.slug,
        "status": t.status,
        "tier": t.tier,
        "plan_code": t.plan_id.code if t.plan_id else None,
        "billing_provider": t.billing_provider,
        "stripe_customer_id": t.stripe_customer_id or None,
        "stripe_subscription_id": t.stripe_subscription_id or None,
        "mrr_usd": t.mrr_usd,
        "seats": t.seats,
        "cabinets_last_30d": t.cabinets_last_30d,
        "marathon_referred": t.marathon_referred,
        "admin_email": t.admin_email,
        "docker_compose_path": t.docker_compose_path or None,
        "caddy_snippet_path": t.caddy_snippet_path or None,
        "created_at": (
            t.created_at.isoformat() if t.created_at else None),
        "provisioned_at": (
            t.provisioned_at.isoformat() if t.provisioned_at else None),
        "suspended_at": (
            t.suspended_at.isoformat() if t.suspended_at else None),
        "cancelled_at": (
            t.cancelled_at.isoformat() if t.cancelled_at else None),
    }


class KitchenForgeSaasTenants(http.Controller):

    # ------------------------------------------------------------------
    # GET /saas/v1/tenants — list
    # ------------------------------------------------------------------
    @http.route(
        "/saas/v1/tenants", type="http", auth="public",
        methods=["GET"], csrf=False)
    @requires_api_key
    def tenants_list(self, **kw):
        domain = []
        status = kw.get("status")
        if status:
            domain.append(("status", "=", status))
        try:
            tenants = request.env["kitchenforge.tenant"].sudo().search(
                domain, limit=200)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("saas tenants list failed")
            return _error("saas_tenants_error", str(exc), 500)
        return _json({
            "tenants": [_tenant_to_dict(t) for t in tenants],
            "count": len(tenants),
        })

    # ------------------------------------------------------------------
    # POST /saas/v1/tenants — create + auto-provision
    # ------------------------------------------------------------------
    @http.route(
        "/saas/v1/tenants", type="http", auth="public",
        methods=["POST"], csrf=False)
    @requires_api_key
    @supports_idempotency
    def tenants_create(self, **_kw):
        try:
            raw = request.httprequest.get_data(as_text=True)
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            return _error("invalid_json", str(exc), 400)
        if not isinstance(body, dict):
            return _error("invalid_body", "expected JSON object", 400)

        required = ("name", "slug", "admin_email")
        missing = [k for k in required if not body.get(k)]
        if missing:
            return _error(
                "missing_fields",
                "Missing required fields: %s" % ", ".join(missing),
                400)

        vals = {
            "name": body["name"],
            "slug": body["slug"],
            "admin_email": body["admin_email"],
            "tier": body.get("tier", "direct"),
            "billing_provider": body.get("billing_provider", "stripe"),
            "marathon_referred": bool(body.get("marathon_referred")),
            "seats": int(body.get("seats", 1)),
        }
        try:
            tenant = request.env["kitchenforge.tenant"].sudo().create(vals)
        except (ValidationError, UserError) as exc:
            return _error("validation_error", str(exc), 400)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("saas tenant create failed")
            return _error("saas_tenants_error", str(exc), 500)

        # Auto-provision unless the caller explicitly asked us not to.
        if body.get("auto_provision", True):
            try:
                tenant.action_provision()
            except (UserError, ValidationError) as exc:
                return _error("provision_error", str(exc), 409)

        return _json({"tenant": _tenant_to_dict(tenant)}, status=201)

    # ------------------------------------------------------------------
    # GET /saas/v1/tenants/<id>
    # ------------------------------------------------------------------
    @http.route(
        "/saas/v1/tenants/<int:tenant_id>", type="http", auth="public",
        methods=["GET"], csrf=False)
    @requires_api_key
    def tenants_get(self, tenant_id, **_kw):
        tenant = request.env["kitchenforge.tenant"].sudo().browse(tenant_id)
        if not tenant.exists():
            return _error("not_found", "tenant %s" % tenant_id, 404)
        return _json({"tenant": _tenant_to_dict(tenant)})

    # ------------------------------------------------------------------
    # POST /saas/v1/tenants/<id>/<action>  (suspend|resume|cancel)
    # ------------------------------------------------------------------
    @http.route(
        ["/saas/v1/tenants/<int:tenant_id>/<string:action>"],
        type="http", auth="public", methods=["POST"], csrf=False)
    @requires_api_key
    @supports_idempotency
    def tenants_action(self, tenant_id, action, **_kw):
        tenant = request.env["kitchenforge.tenant"].sudo().browse(tenant_id)
        if not tenant.exists():
            return _error("not_found", "tenant %s" % tenant_id, 404)

        handlers = {
            "suspend": tenant.action_suspend,
            "resume": tenant.action_resume,
            "cancel": tenant.action_cancel,
            "provision": tenant.action_provision,
        }
        handler = handlers.get(action)
        if handler is None:
            return _error(
                "unknown_action",
                "Action %r not in %s" % (action, list(handlers)),
                400)
        try:
            handler()
        except (UserError, ValidationError) as exc:
            return _error("action_error", str(exc), 409)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("saas tenant %s %s failed", tenant_id, action)
            return _error("saas_tenants_error", str(exc), 500)
        return _json({"tenant": _tenant_to_dict(tenant), "action": action})
