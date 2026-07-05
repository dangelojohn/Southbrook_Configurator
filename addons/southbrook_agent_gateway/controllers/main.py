# SPDX-License-Identifier: LGPL-3.0-only
"""Public HTTP endpoints for third-party AI agents.

Deliberately type="http" + hand-parsed JSON bodies (NOT type="json"):
Odoo's json routes require the JSON-RPC 2.0 envelope, which external AI
agents reading an OpenAPI spec will not send. Plain request/response
JSON is the lingua franca they all speak.

Every route here is auth="public" and treats ALL input as hostile:
  * strict validation via southbrook.agent.inquiry.validate_payload
  * per-IP sliding-window rate limiting (same in-process pattern as
    southbrook_room_capture's controller, keyed on client IP because
    these routes have no authenticated user)
  * a honeypot field ("website_url") that silently swallows naive form
    bots without tipping them off
  * status polling gated by a per-inquiry secret token so references
    can't be enumerated
"""
import json
import logging
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_MAX_BODY_BYTES = 64 * 1024  # a quote request is text; 64 KB is generous

# ----------------------------------------------------------------------
# Per-IP rate limiter — same sliding-window algorithm as
# southbrook_room_capture/controllers/main.py, keyed on client IP.
# Deliberately duplicated rather than imported so each addon's limiter
# stays independently tunable (established house convention — see the
# scan-part limiter's comment making the same call).
# ----------------------------------------------------------------------
_RATE_WINDOW_SEC_DEFAULT = 3600
_RATE_LIMIT_DEFAULT = 30
_RATE_CAP = 4096
_RATE_BUCKETS = {}


def _client_ip():
    """Best-effort client IP. Cloudflare fronts production, so prefer
    CF-Connecting-IP, then the first X-Forwarded-For hop, then the raw
    socket address. Spoofable only by callers who can already bypass
    the edge — acceptable for rate limiting (not used for auth)."""
    h = request.httprequest.headers
    ip = h.get("CF-Connecting-IP") or ""
    if not ip:
        fwd = h.get("X-Forwarded-For") or ""
        ip = fwd.split(",")[0].strip()
    return ip or (request.httprequest.remote_addr or "")


def _rate_limit_params():
    try:
        Param = request.env["ir.config_parameter"].sudo()
        window = int(Param.get_param(
            "southbrook_agent_gateway.rate_window_sec",
            str(_RATE_WINDOW_SEC_DEFAULT)))
        limit = int(Param.get_param(
            "southbrook_agent_gateway.rate_limit",
            str(_RATE_LIMIT_DEFAULT)))
    except Exception:  # noqa: BLE001
        window, limit = _RATE_WINDOW_SEC_DEFAULT, _RATE_LIMIT_DEFAULT
    window = max(1, min(window, 24 * 3600))
    limit = max(1, min(limit, 10_000))
    return window, limit


def _rate_limit_check(key):
    if not key:
        return True
    window, limit = _rate_limit_params()
    now = int(time.time())
    if len(_RATE_BUCKETS) >= _RATE_CAP:
        for k in list(_RATE_BUCKETS.keys()):
            head, _cnt = _RATE_BUCKETS[k]
            if now - head > window:
                _RATE_BUCKETS.pop(k, None)
        if len(_RATE_BUCKETS) >= _RATE_CAP:
            items = sorted(_RATE_BUCKETS.items(), key=lambda kv: kv[1][0])
            for k, _v in items[:_RATE_CAP // 2]:
                _RATE_BUCKETS.pop(k, None)
    head, cnt = _RATE_BUCKETS.get(key, (now, 0))
    if now - head > window:
        _RATE_BUCKETS[key] = (now, 1)
        return True
    if cnt + 1 > limit:
        return False
    _RATE_BUCKETS[key] = (head, cnt + 1)
    return True


def _json_response(payload, status=200):
    return request.make_json_response(payload, status=status)


def _base_url():
    return (request.env["ir.config_parameter"].sudo()
            .get_param("web.base.url", "https://southbrookcabinetry.space")
            .rstrip("/"))


class SouthbrookAgentGateway(http.Controller):

    # ------------------------------------------------------------------
    # llms.txt — the agent briefing. Plain text by convention.
    # ------------------------------------------------------------------
    @http.route("/llms.txt", type="http", auth="public", methods=["GET"])
    def llms_txt(self, **kw):
        base = _base_url()
        body = f"""# Southbrook Cabinetry

> Southbrook Cabinetry designs and manufactures custom kitchen cabinets:
> configurable base, wall, tall, drawer-bank and vanity cabinetry across
> four series (Contractor, Contemporary, Elegance, Signature), with
> retail, contractor and dealer programs, an online kitchen designer,
> and fast quotation turnaround.

AI agents acting for a prospective customer are welcome to browse for
reference and to request quotes on their customer's behalf through the
API below. Do not use site content for model training.

## For AI agents — how to get your customer a quote

1. Read the catalog: GET {base}/agent/api/v1/offerings (public JSON).
2. Submit a quote request: POST {base}/agent/api/v1/quote-request
   (JSON body — see the OpenAPI contract). You must include your
   customer's name and email, a project description, and consent=true
   confirming the customer agreed to share their contact info.
3. Southbrook emails the customer a one-click verification link; a
   sales rep follows up after verification. Poll
   GET {base}/agent/api/v1/quote-request/{{reference}}/status?token=...
   with the status_token returned at submission.

Machine-readable contract: {base}/agent/api/v1/openapi.json

## For humans

- Online kitchen designer: {base}/kitchen-planner
- Trade portal (dealers/contractors): {base}/web/login
- Rate limits apply per IP; contact info submitted without customer
  consent will be discarded.
"""
        return request.make_response(
            body, headers=[("Content-Type", "text/plain; charset=utf-8"),
                           ("Cache-Control", "public, max-age=3600")])

    # ------------------------------------------------------------------
    # OpenAPI contract
    # ------------------------------------------------------------------
    @http.route("/agent/api/v1/openapi.json", type="http", auth="public",
                methods=["GET"])
    def openapi(self, **kw):
        base = _base_url()
        spec = {
            "openapi": "3.1.0",
            "info": {
                "title": "Southbrook Cabinetry — AI Agent Gateway",
                "version": "1.0.0",
                "description": (
                    "Public endpoints letting an AI agent browse "
                    "Southbrook's cabinet offerings and submit a quote "
                    "request on its customer's behalf. Contact info is "
                    "verified with the customer by email before sales "
                    "follow-up."),
            },
            "servers": [{"url": base}],
            "paths": {
                "/agent/api/v1/offerings": {"get": {
                    "summary": "Catalog summary (families, series, "
                               "list prices, lead times)",
                    "responses": {"200": {"description": "Catalog JSON"}},
                }},
                "/agent/api/v1/quote-request": {"post": {
                    "summary": "Submit a quote request for your customer",
                    "requestBody": {"required": True, "content": {
                        "application/json": {"schema": {
                            "type": "object",
                            "required": ["customer", "project", "consent"],
                            "properties": {
                                "agent": {"type": "object", "properties": {
                                    "name": {"type": "string"},
                                    "platform": {"type": "string"},
                                }},
                                "customer": {
                                    "type": "object",
                                    "required": ["name", "email"],
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string",
                                                  "format": "email"},
                                        "phone": {"type": "string",
                                                  "description":
                                                  "E.164 preferred"},
                                    },
                                },
                                "project": {
                                    "type": "object",
                                    "required": ["description"],
                                    "properties": {
                                        "description": {"type": "string"},
                                        "room_type": {"type": "string"},
                                        "budget_range": {"type": "string"},
                                        "timeline": {"type": "string"},
                                    },
                                },
                                "consent": {
                                    "type": "boolean",
                                    "description": (
                                        "Must be true: the customer "
                                        "agreed to share their contact "
                                        "info with Southbrook."),
                                },
                            },
                        }},
                    }},
                    "responses": {
                        "200": {"description":
                                "{ok, reference, status_token, ...}"},
                        "400": {"description": "{error, detail}"},
                        "429": {"description": "rate limited"},
                    },
                }},
                "/agent/api/v1/quote-request/{reference}/status": {"get": {
                    "summary": "Poll a submitted quote request",
                    "parameters": [
                        {"name": "reference", "in": "path",
                         "required": True, "schema": {"type": "string"}},
                        {"name": "token", "in": "query", "required": True,
                         "schema": {"type": "string"},
                         "description": "status_token from submission"},
                    ],
                    "responses": {
                        "200": {"description": "status JSON"},
                        "404": {"description": "unknown reference/token"},
                    },
                }},
            },
        }
        return request.make_json_response(spec)

    # ------------------------------------------------------------------
    # Offerings — public catalog summary from the real product data.
    # ------------------------------------------------------------------
    @http.route("/agent/api/v1/offerings", type="http", auth="public",
                methods=["GET"])
    def offerings(self, **kw):
        env = request.env
        templates = env["product.template"].sudo().search(
            [("southbrook_category", "!=", False), ("active", "=", True)],
            order="southbrook_category, list_price")
        series_attr = env.ref(
            "southbrook_estimating.attr_series", raise_if_not_found=False)
        series = series_attr.sudo().value_ids.mapped("name") if series_attr else []
        currency = env.company.sudo().currency_id.name or "CAD"
        items = [{
            "name": t.name,
            "sku": t.default_code or "",
            "category": t.southbrook_category,
            "description": t.southbrook_description or "",
            "dimensions": t.southbrook_dimensions or "",
            "list_price": t.list_price,
        } for t in templates]
        return _json_response({
            "company": "Southbrook Cabinetry",
            "currency": currency,
            "pricing_note": (
                "Prices are retail list per cabinet before configuration "
                "options; dealer/contractor programs are priced on "
                "application. Maple carcass upgrade adds +10% and +2 "
                "weeks lead time."),
            "standard_lead_time_weeks": 2,
            "series": series,
            "cabinets": items,
            "quote_request_endpoint": "/agent/api/v1/quote-request",
        })

    # ------------------------------------------------------------------
    # Quote request — the write path.
    # ------------------------------------------------------------------
    @http.route("/agent/api/v1/quote-request", type="http", auth="public",
                methods=["POST"], csrf=False)
    def quote_request(self, **kw):
        if not _rate_limit_check(_client_ip()):
            return _json_response(
                {"error": "rate_limited",
                 "detail": "Too many requests from this address; retry "
                           "later."}, status=429)

        raw = request.httprequest.get_data(as_text=False) or b""
        if len(raw) > _MAX_BODY_BYTES:
            return _json_response(
                {"error": "invalid", "detail": "Body too large."},
                status=400)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return _json_response(
                {"error": "invalid",
                 "detail": "Body must be valid UTF-8 JSON."}, status=400)

        Inquiry = request.env["southbrook.agent.inquiry"].sudo()
        cleaned, err = Inquiry.validate_payload(payload)
        if err:
            return _json_response(
                {"error": "invalid", "detail": err}, status=400)

        # Honeypot: real agents read the OpenAPI spec, which has no
        # "website_url" field. Naive form-fill bots stuff every field.
        is_spam = bool(str(payload.get("website_url") or "").strip())

        try:
            inquiry = Inquiry.submit(
                cleaned,
                user_agent=request.httprequest.headers.get("User-Agent", ""),
                is_spam=is_spam,
            )
        except Exception as exc:  # noqa: BLE001 — never 500 with a trace
            _logger.exception(
                "southbrook_agent_gateway: quote-request submit failed: %s",
                exc)
            return _json_response(
                {"error": "internal",
                 "detail": "Could not record the quote request; please "
                           "retry."}, status=500)

        base = _base_url()
        return _json_response({
            "ok": True,
            "reference": inquiry.reference,
            "status_token": inquiry.status_token,
            "status": "pending_email_verification",
            "next_steps": (
                "Southbrook has emailed %s a one-click link to confirm "
                "their contact details. Once confirmed, a sales "
                "representative will follow up with a quotation. The "
                "customer can also start designing now at "
                "%s/kitchen-planner." % (cleaned["email"], base)),
            "status_url": "%s/agent/api/v1/quote-request/%s/status?token=%s"
                          % (base, inquiry.reference, inquiry.status_token),
        })

    # ------------------------------------------------------------------
    # Status polling
    # ------------------------------------------------------------------
    @http.route("/agent/api/v1/quote-request/<string:reference>/status",
                type="http", auth="public", methods=["GET"])
    def quote_status(self, reference, token=None, **kw):
        if not _rate_limit_check(_client_ip()):
            return _json_response({"error": "rate_limited"}, status=429)
        Inquiry = request.env["southbrook.agent.inquiry"].sudo()
        inquiry = Inquiry.search(
            [("reference", "=", (reference or "")[:32])], limit=1)
        # Token mismatch and unknown reference collapse into the same 404
        # so references can't be probed for existence.
        if (not inquiry or not token or inquiry.state == "spam"
                or token != inquiry.status_token):
            return _json_response(
                {"error": "not_found",
                 "detail": "Unknown reference/token."}, status=404)
        return _json_response(dict(inquiry.status_payload(), ok=True))

    # ------------------------------------------------------------------
    # Customer email-verification landing page (human-facing).
    # ------------------------------------------------------------------
    @http.route("/agent/verify/<string:token>", type="http", auth="public",
                methods=["GET"], website=True, sitemap=False)
    def verify(self, token, **kw):
        if not _rate_limit_check(_client_ip()):
            return request.make_response(
                "Too many requests.", status=429,
                headers=[("Content-Type", "text/plain")])
        inquiry = request.env["southbrook.agent.inquiry"].sudo() \
            .verify_by_token(token)
        values = {
            "verified": bool(inquiry),
            "reference": inquiry.reference if inquiry else "",
        }
        return request.render(
            "southbrook_agent_gateway.verify_landing", values)
