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
import hmac
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
# SEPARATE buckets per concern (2026-07-05 code-review fix): a single
# shared per-IP bucket let the documented status-polling loop (which
# llms.txt tells agents to run) exhaust the budget and 429 the human
# customer's one-time verification click behind the same NAT/edge IP.
# Each concern now has its own bucket + its own tunable limit:
#   write  — quote/quote-request (expensive; strict)
#   read   — offerings + status polling (cheap; generous)
#   verify — the customer's email-confirm click (human; very generous)
_RATE_CAP = 4096
_RATE_DEFAULTS = {
    "write": (3600, 30),
    "read": (3600, 300),
    "verify": (3600, 60),
}
_RATE_BUCKETS = {"write": {}, "read": {}, "verify": {}}


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


def _rate_limit_params(kind):
    win_default, lim_default = _RATE_DEFAULTS[kind]
    try:
        Param = request.env["ir.config_parameter"].sudo()
        window = int(Param.get_param(
            "southbrook_agent_gateway.%s_rate_window_sec" % kind,
            str(win_default)))
        limit = int(Param.get_param(
            "southbrook_agent_gateway.%s_rate_limit" % kind,
            str(lim_default)))
    except Exception:  # noqa: BLE001
        window, limit = win_default, lim_default
    window = max(1, min(window, 24 * 3600))
    limit = max(1, min(limit, 100_000))
    return window, limit


def _rate_limit_check(key, kind="write"):
    if not key:
        return True
    bucket = _RATE_BUCKETS[kind]
    window, limit = _rate_limit_params(kind)
    now = int(time.time())
    if len(bucket) >= _RATE_CAP:
        for k in list(bucket.keys()):
            head, _cnt = bucket[k]
            if now - head > window:
                bucket.pop(k, None)
        if len(bucket) >= _RATE_CAP:
            items = sorted(bucket.items(), key=lambda kv: kv[1][0])
            for k, _v in items[:_RATE_CAP // 2]:
                bucket.pop(k, None)
    head, cnt = bucket.get(key, (now, 0))
    if now - head > window:
        bucket[key] = (now, 1)
        return True
    if cnt + 1 > limit:
        return False
    bucket[key] = (head, cnt + 1)
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
   Each cabinet has a `sku` and retail `list_price`.
2. Choose ONE of:
   a. Lead only — POST {base}/agent/api/v1/quote-request. Include the
      customer's name + email, a project description, and consent=true.
      A Southbrook rep prepares and sends the quotation.
   b. Instant priced quote — POST {base}/agent/api/v1/quote with the
      same body PLUS line_items: [{{"sku": "SB-BASE-1DR", "qty": 4}}, ...]
      using SKUs from the catalog. The response includes a `quote`
      object with per-line prices, subtotal and total. The draft
      quotation is submitted for review — never auto-confirmed.
   Optionally include an `address` object (street, city, state, zip,
   country) in either request.
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
                    "summary": "Submit a quote request (lead only — a "
                               "Southbrook rep quotes the customer back)",
                    "requestBody": {"required": True, "content": {
                        "application/json": {"schema": {
                            "$ref": "#/components/schemas/QuoteRequest"}}}},
                    "responses": {
                        "200": {"description":
                                "{ok, reference, status_token, ...}"},
                        "400": {"description": "{error, detail}"},
                        "429": {"description": "rate limited"},
                    },
                }},
                "/agent/api/v1/quote": {"post": {
                    "summary": "Create a self-service draft quotation NOW "
                               "with priced line items (requires line_items)",
                    "description": (
                        "Same body as /quote-request PLUS a required "
                        "line_items array of {sku, qty} using SKUs from "
                        "/offerings. Returns the same fields plus a "
                        "`quote` object: quote_reference, per-line prices, "
                        "subtotal and total. The quotation is submitted "
                        "for review by a Southbrook rep — it is never "
                        "auto-confirmed."),
                    "requestBody": {"required": True, "content": {
                        "application/json": {"schema": {
                            "$ref": "#/components/schemas/QuoteWithItems"}}}},
                    "responses": {
                        "200": {"description":
                                "{ok, reference, status_token, quote, ...}"},
                        "400": {"description": "{error, detail}"},
                        "429": {"description": "rate limited"},
                    },
                }},
                "/agent/api/v1/quote-request/{reference}/status": {"get": {
                    "summary": "Poll a submitted request (lead or quote)",
                    "parameters": [
                        {"name": "reference", "in": "path",
                         "required": True, "schema": {"type": "string"}},
                        {"name": "token", "in": "query", "required": True,
                         "schema": {"type": "string"},
                         "description": "status_token from submission"},
                    ],
                    "responses": {
                        "200": {"description": "status JSON (includes "
                                "`quote` when items were submitted)"},
                        "404": {"description": "unknown reference/token"},
                    },
                }},
            },
            "components": {"schemas": {
                "QuoteRequest": {
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
                                          "description": "E.164 preferred"},
                            },
                        },
                        "address": {
                            "type": "object",
                            "description": "Optional — helps service-area "
                                           "triage and the final quotation.",
                            "properties": {
                                "street": {"type": "string"},
                                "city": {"type": "string"},
                                "state": {"type": "string",
                                          "description":
                                          "state/province name or code"},
                                "zip": {"type": "string"},
                                "country": {"type": "string",
                                            "description":
                                            "name or ISO-2 code"},
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
                            "description": ("Must be true: the customer "
                                            "agreed to share their contact "
                                            "info with Southbrook."),
                        },
                    },
                },
                "QuoteWithItems": {
                    "allOf": [
                        {"$ref": "#/components/schemas/QuoteRequest"},
                        {"type": "object", "required": ["line_items"],
                         "properties": {"line_items": {
                             "type": "array",
                             "minItems": 1,
                             "items": {
                                 "type": "object",
                                 "required": ["sku"],
                                 "properties": {
                                     "sku": {"type": "string",
                                             "description":
                                             "a SKU from /offerings"},
                                     "qty": {"type": "integer",
                                             "minimum": 1, "default": 1},
                                 },
                             }}}},
                    ],
                },
            }},
        }
        return request.make_json_response(spec)

    # ------------------------------------------------------------------
    # Offerings — public catalog summary from the real product data.
    # ------------------------------------------------------------------
    @http.route("/agent/api/v1/offerings", type="http", auth="public",
                methods=["GET"])
    def offerings(self, **kw):
        # Rate-limited (read bucket) so an unauthenticated caller can't
        # hammer this sudo full-table search (2026-07-05 code-review fix).
        if not _rate_limit_check(_client_ip(), kind="read"):
            return _json_response({"error": "rate_limited"}, status=429)
        env = request.env
        # Filter on sale_ok so internal-only / not-for-sale templates that
        # happen to carry a southbrook_category never leak to the public
        # (2026-07-05 code-review fix — was southbrook_category+active only,
        # exposing unpublished products + prices).
        templates = env["product.template"].sudo().search(
            [("southbrook_category", "!=", False),
             ("active", "=", True),
             ("sale_ok", "=", True)],
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
            "instant_quote_endpoint": "/agent/api/v1/quote",
            "instant_quote_note": (
                "POST /agent/api/v1/quote with line_items [{sku, qty}] "
                "(SKUs from this list) to create a priced draft quotation "
                "for your customer immediately."),
        })

    # ------------------------------------------------------------------
    # Write paths. Two endpoints share one handler:
    #   /quote-request  — lead only (human quotes the customer back)
    #   /quote          — lead + a self-service draft quotation the agent
    #                     gets priced immediately (requires line_items)
    # ------------------------------------------------------------------
    def _read_json_body(self):
        """Return (payload_dict, None) or (None, error_response)."""
        raw = request.httprequest.get_data(as_text=False) or b""
        if len(raw) > _MAX_BODY_BYTES:
            return None, _json_response(
                {"error": "invalid", "detail": "Body too large."},
                status=400)
        try:
            return json.loads(raw.decode("utf-8")), None
        except (ValueError, UnicodeDecodeError):
            return None, _json_response(
                {"error": "invalid",
                 "detail": "Body must be valid UTF-8 JSON."}, status=400)

    def _handle_submission(self, require_line_items):
        if not _rate_limit_check(_client_ip()):
            return _json_response(
                {"error": "rate_limited",
                 "detail": "Too many requests from this address; retry "
                           "later."}, status=429)

        payload, err_resp = self._read_json_body()
        if err_resp is not None:
            return err_resp

        Inquiry = request.env["southbrook.agent.inquiry"].sudo()
        cleaned, err = Inquiry.validate_payload(payload)
        if err:
            return _json_response(
                {"error": "invalid", "detail": err}, status=400)

        line_items, lerr = Inquiry.validate_line_items(
            payload.get("line_items"))
        if lerr:
            return _json_response(
                {"error": "invalid", "detail": lerr}, status=400)
        if require_line_items and not line_items:
            return _json_response(
                {"error": "invalid",
                 "detail": "line_items is required for /quote — a list of "
                           "{sku, qty} using SKUs from "
                           "/agent/api/v1/offerings. For a lead without a "
                           "priced quote, use /quote-request instead."},
                status=400)

        # Honeypot: real agents read the OpenAPI spec, which has no
        # "website_url" field. Naive form-fill bots stuff every field.
        is_spam = bool(str(payload.get("website_url") or "").strip())

        try:
            inquiry = Inquiry.submit(
                cleaned,
                user_agent=request.httprequest.headers.get("User-Agent", ""),
                is_spam=is_spam,
                line_items=line_items,
            )
        except Exception as exc:  # noqa: BLE001 — never 500 with a trace
            _logger.exception(
                "southbrook_agent_gateway: submit failed: %s", exc)
            return _json_response(
                {"error": "internal",
                 "detail": "Could not record the request; please retry."},
                status=500)

        base = _base_url()
        resp = {
            "ok": True,
            "reference": inquiry.reference,
            "status_token": inquiry.status_token,
            "status": "pending_email_verification",
            "next_steps": (
                "Southbrook has emailed %s a one-click link to confirm "
                "their contact details. Once confirmed, a sales "
                "representative will follow up. The customer can also "
                "start designing now at %s/kitchen-planner."
                % (cleaned["email"], base)),
            "status_url": "%s/agent/api/v1/quote-request/%s/status?token=%s"
                          % (base, inquiry.reference, inquiry.status_token),
        }
        if inquiry.sale_order_id:
            resp["quote"] = inquiry.quote_summary()
        return _json_response(resp)

    @http.route("/agent/api/v1/quote-request", type="http", auth="public",
                methods=["POST"], csrf=False)
    def quote_request(self, **kw):
        return self._handle_submission(require_line_items=False)

    @http.route("/agent/api/v1/quote", type="http", auth="public",
                methods=["POST"], csrf=False)
    def quote(self, **kw):
        return self._handle_submission(require_line_items=True)

    # ------------------------------------------------------------------
    # Status polling
    # ------------------------------------------------------------------
    @http.route("/agent/api/v1/quote-request/<string:reference>/status",
                type="http", auth="public", methods=["GET"])
    def quote_status(self, reference, token=None, **kw):
        if not _rate_limit_check(_client_ip(), kind="read"):
            return _json_response({"error": "rate_limited"}, status=429)
        Inquiry = request.env["southbrook.agent.inquiry"].sudo()
        inquiry = Inquiry.search(
            [("reference", "=", (reference or "")[:32])], limit=1)
        # Unknown reference and wrong token collapse into the same 404 so
        # references can't be probed for existence. NOTE (2026-07-05
        # code-review fix): a spam (honeypot) inquiry with the CORRECT
        # token must NOT 404 — submit() deliberately returns a
        # success-shaped response for honeypot hits "so the bot learns
        # nothing", and a status route that then 404'd would be exactly
        # the oracle that tells the bot it was flagged. Constant-time
        # token compare, and spam is reported with a benign pending
        # status identical to a real not-yet-verified inquiry.
        token_ok = bool(inquiry and token and hmac.compare_digest(
            inquiry.status_token or "", token))
        if not token_ok:
            return _json_response(
                {"error": "not_found",
                 "detail": "Unknown reference/token."}, status=404)
        if inquiry.state == "spam":
            return _json_response({
                "ok": True,
                "reference": inquiry.reference,
                "state": "new",
                "email_verified": False,
                "sales_stage": "New",
                "assigned": False,
            })
        return _json_response(dict(inquiry.status_payload(), ok=True))

    # ------------------------------------------------------------------
    # Customer email-verification landing page (human-facing).
    # ------------------------------------------------------------------
    @http.route("/agent/verify/<string:token>", type="http", auth="public",
                methods=["GET"], website=True, sitemap=False)
    def verify(self, token, **kw):
        if not _rate_limit_check(_client_ip(), kind="verify"):
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
