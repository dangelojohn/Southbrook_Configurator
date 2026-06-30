# SPDX-License-Identifier: LGPL-3.0-only
"""W072 (R8.3, 2026-06-27) — Floor-action mini-framework dispatcher.

Two routes, both public:

  GET  /sb/floor/<action>?p=<payload>           -> render kind's HTML form
  POST /sb/floor/<action>/submit                -> dispatch to kind handler

Both routes:
  1. Look up the kind handler (404 if unknown).
  2. Parse + verify HMAC on the payload (refuse forged/tampered QRs).
  3. Enforce expected QR kind (each floor action declares which sb://
     kind it consumes — POD wants 'ship', install_check wants 'ship',
     temp_labor_signin wants 'loc').
  4. Resolve the backing record via the kind's get_record.
  5. Rate-limit per source IP (in-process ring; bounded memory).
  6. Append to southbrook.qr.scan.log with the kind/action/result.
  7. Hand to render_form (GET) or handle_submit (POST).

The framework is the security perimeter for these public flows. Kinds
must not bypass it — every public floor surface in qr_kit should route
through /sb/floor/<action> exclusively. (The legacy /sb/qr/pod routes
still exist for backward compat with existing QR labels in the field.)
"""
import json
import logging
import time

from odoo import http
from odoo.http import request


_logger = logging.getLogger(__name__)

# In-process per-IP rate-limit. Each entry is (timestamps_deque_head_ts,
# count). Bounded to _RATE_CAP IPs; LRU-trimmed when full. The token-
# bucket math is simple "N requests per WINDOW seconds" — anything
# stricter belongs in a real reverse-proxy WAF (Cloudflare, etc.).
_RATE_WINDOW_SEC_DEFAULT = 60
_RATE_LIMIT_DEFAULT = 30
_RATE_CAP = 4096
_RATE_BUCKETS = {}


def _rate_limit_params():
    """Read window + limit from ICP. Defaults: 30 req / 60 s / IP."""
    try:
        Param = request.env["ir.config_parameter"].sudo()
        window = int(
            Param.get_param("southbrook.floor_action.rate_window_sec",
                            str(_RATE_WINDOW_SEC_DEFAULT)))
        limit = int(
            Param.get_param("southbrook.floor_action.rate_limit",
                            str(_RATE_LIMIT_DEFAULT)))
    except Exception:  # noqa: BLE001
        window, limit = _RATE_WINDOW_SEC_DEFAULT, _RATE_LIMIT_DEFAULT
    window = max(1, min(window, 3600))
    limit = max(1, min(limit, 10_000))
    return window, limit


def _rate_limit_check(ip):
    """Return True if the IP is within budget, False if it exceeded.

    Side effect: bumps the counter on True. Trims expired entries when
    the cap is near.
    """
    if not ip:
        return True  # don't block requests with no source IP — log only
    window, limit = _rate_limit_params()
    now = int(time.time())
    # Lazy GC near cap.
    if len(_RATE_BUCKETS) >= _RATE_CAP:
        for k in list(_RATE_BUCKETS.keys()):
            head, _cnt = _RATE_BUCKETS[k]
            if now - head > window:
                _RATE_BUCKETS.pop(k, None)
        if len(_RATE_BUCKETS) >= _RATE_CAP:
            # Drop oldest half.
            items = sorted(_RATE_BUCKETS.items(), key=lambda kv: kv[1][0])
            for k, _v in items[:_RATE_CAP // 2]:
                _RATE_BUCKETS.pop(k, None)
    head, cnt = _RATE_BUCKETS.get(ip, (now, 0))
    if now - head > window:
        # Window expired — reset.
        _RATE_BUCKETS[ip] = (now, 1)
        return True
    if cnt + 1 > limit:
        return False
    _RATE_BUCKETS[ip] = (head, cnt + 1)
    return True


def _log_floor(env, kind_handler, payload, action, result, error=None,
               target_id=None):
    """Append a row to southbrook.qr.scan.log. Best-effort: a logging
    failure must NEVER block the user-facing response."""
    try:
        Log = env["southbrook.qr.scan.log"].sudo()
        Log.create({
            "kind": getattr(kind_handler, "_expected_qr_kind", None)
                    or "floor",
            "action": "floor:%s" % action,
            "result": result,
            "error_message": (error or "")[:255] if error else False,
            "target_model": getattr(kind_handler, "_target_model", False)
                            or False,
            "target_id": target_id or 0,
            "payload": (payload or "")[:500],
            "source_ip": request.httprequest.remote_addr,
            "user_agent": (
                request.httprequest.headers.get("User-Agent")
                or "")[:255],
        })
    except Exception:  # noqa: BLE001
        _logger.exception("Floor-action scan-log write failed")


def _plain(text, status=200):
    """Helper — return a plain-text http response."""
    return request.make_response(
        text, status=status,
        headers=[("Content-Type", "text/plain; charset=utf-8")])


def _html(body, status=200):
    return request.make_response(
        body, status=status,
        headers=[("Content-Type", "text/html; charset=utf-8")])


class FloorActionController(http.Controller):

    @http.route("/sb/floor/<string:action>", type="http", auth="public",
                methods=["GET"], csrf=False, website=False)
    def floor_render(self, action=None, p=None, **kw):
        """Render the kind's HTML form. Same gate as POD: HMAC on the
        payload is the auth; we never trust raw URL params."""
        env = request.env
        ip = request.httprequest.remote_addr
        if not _rate_limit_check(ip):
            return _plain("Rate limit exceeded. Try again shortly.",
                          status=429)
        Kind = env["southbrook.floor.action.kind"]
        handler = Kind.resolve_kind(action)
        # NB(v19): `resolve_kind` returns the literal ``False`` sentinel
        # when the action slug is not registered, OR the env-bound
        # AbstractModel handler when it IS registered. In Odoo 19 every
        # AbstractModel is an empty recordset and `bool(empty_recordset)`
        # is False, so a plain ``if not handler:`` mis-fires on a
        # registered kind — see memory note
        # [odoo19_abstract_model_falsy_recordset] and the parallel fix
        # in qr_scan.py for `southbrook.qr.kind` (commit b7f21b9). The
        # ``is False`` discriminator fires only on the explicit sentinel.
        if handler is False:
            _log_floor(env, None, p or "", action or "", "unknown_kind",
                       error="No handler for action=%r" % action)
            return _plain("Unknown floor action: %s" % action, status=404)
        if not p:
            _log_floor(env, handler, "", action, "error",
                       error="Missing payload")
            return _plain("Missing ?p=<qr_payload>", status=400)
        try:
            parsed = env["southbrook.qr.payload"].sudo().parse(p)
        except Exception as exc:  # noqa: BLE001
            _log_floor(env, handler, p, action, "error",
                       error="parse: %s" % exc)
            return _plain("Bad QR: %s" % exc, status=400)
        if not parsed.get("valid_signature"):
            _log_floor(env, handler, p, action, "invalid_signature",
                       error="HMAC mismatch")
            return _plain(
                "Invalid QR signature — forged or tampered.", status=403)
        expected = handler._expected_qr_kind
        if expected and parsed.get("kind") != expected:
            _log_floor(env, handler, p, action, "unknown_kind",
                       error="want kind=%r got %r" % (
                           expected, parsed.get("kind")))
            return _plain(
                "Floor action '%s' expects '%s' kind (got '%s')."
                % (action, expected, parsed.get("kind")),
                status=400)
        try:
            record = handler.get_record(parsed)
        except Exception as exc:  # noqa: BLE001
            _log_floor(env, handler, p, action, "record_not_found",
                       error=str(exc))
            return _plain(str(exc), status=404)
        try:
            body_or_resp = handler.render_form(p, record)
        except NotImplementedError as exc:
            _log_floor(env, handler, p, action, "unknown_action",
                       error=str(exc),
                       target_id=record.id if record else 0)
            return _plain(str(exc), status=501)
        except Exception as exc:  # noqa: BLE001
            _log_floor(env, handler, p, action, "error", error=str(exc),
                       target_id=record.id if record else 0)
            return _plain(str(exc), status=500)
        _log_floor(env, handler, p, action, "ok",
                   target_id=record.id if record else 0)
        # render_form may return a string OR a full Response (the POD
        # kind returns request.make_response — preserve it as-is).
        if hasattr(body_or_resp, "status_code"):
            return body_or_resp
        if not str(body_or_resp).lstrip().lower().startswith("<!doctype"):
            body_or_resp = "<!DOCTYPE html>\n" + str(body_or_resp)
        return _html(body_or_resp)

    @http.route("/sb/floor/<string:action>/submit", type="json",
                auth="public", methods=["POST"], csrf=False)
    def floor_submit(self, action=None, **body):
        """Process the kind's submission. JSON in, JSON out.

        Body shape (kind-defined; framework only requires `payload`):
          { "payload": "sb://...", ... }

        Response shape:
          { "ok": bool, "message"?: "...", "error"?: "..." }
        """
        env = request.env
        ip = request.httprequest.remote_addr
        if not _rate_limit_check(ip):
            return {"ok": False, "error":
                    "Rate limit exceeded. Try again shortly."}
        Kind = env["southbrook.floor.action.kind"]
        handler = Kind.resolve_kind(action)
        # See identical note above on floor_render — `is False` is the
        # only correct discriminator against the v19 AbstractModel
        # falsy-recordset trap.
        if handler is False:
            _log_floor(env, None, "", action or "", "unknown_kind",
                       error="No handler for action=%r" % action)
            return {"ok": False, "error":
                    "Unknown floor action: %s" % action}
        payload = body.get("payload")
        if not payload:
            _log_floor(env, handler, "", action, "error",
                       error="Missing payload in body")
            return {"ok": False, "error": "missing payload"}
        try:
            parsed = env["southbrook.qr.payload"].sudo().parse(payload)
        except Exception as exc:  # noqa: BLE001
            _log_floor(env, handler, payload, action, "error",
                       error="parse: %s" % exc)
            return {"ok": False, "error": "parse: %s" % exc}
        if not parsed.get("valid_signature"):
            _log_floor(env, handler, payload, action, "invalid_signature",
                       error="HMAC mismatch")
            return {"ok": False, "error": "Invalid signature"}
        expected = handler._expected_qr_kind
        if expected and parsed.get("kind") != expected:
            _log_floor(env, handler, payload, action, "unknown_kind",
                       error="want kind=%r got %r" % (
                           expected, parsed.get("kind")))
            return {"ok": False,
                    "error": "Action '%s' expects '%s' kind (got '%s')"
                    % (action, expected, parsed.get("kind"))}
        try:
            record = handler.get_record(parsed)
        except Exception as exc:  # noqa: BLE001
            _log_floor(env, handler, payload, action, "record_not_found",
                       error=str(exc))
            return {"ok": False, "error": str(exc)}
        try:
            result = handler.handle_submit(payload, record, body)
        except NotImplementedError as exc:
            _log_floor(env, handler, payload, action, "unknown_action",
                       error=str(exc),
                       target_id=record.id if record else 0)
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            _log_floor(env, handler, payload, action, "error",
                       error=str(exc),
                       target_id=record.id if record else 0)
            return {"ok": False, "error": str(exc)}
        ok = bool(result.get("ok"))
        _log_floor(env, handler, payload, action,
                   "ok" if ok else "error",
                   error=result.get("error"),
                   target_id=record.id if record else 0)
        return result
