# SPDX-License-Identifier: LGPL-3.0-only
"""Controllers — /sb/qr/scan resolves any signed QR.

Two endpoints:
  GET  /sb/qr/scan?p=<payload>          — HTML redirect (tablet browser)
  POST /sb/qr/scan                       — JSON API (mobile / handheld scanner)

POST body:
  {
    "payload": "sb://...",
    "action": "open" | <kind-specific>,
    "params": { ... }       # optional, passed to handle_action
  }

JSON response shape:
  {
    "ok": bool,
    "result": "ok" | "invalid_signature" | "expired" | "unknown_kind" | ...,
    "record_name": "...",   # when ok
    "record_id": 123,
    "model": "southbrook.asbuilt",
    "redirect": "/odoo/...",
    "error": "..."          # when not ok
  }

Time-bound expiry:
  Per-kind handler can set _expires_in_seconds. Controller checks
  payload.ts + ttl against current time. Expired payloads are logged
  with result='expired'.
"""
import json
import logging
import time

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request

_logger = logging.getLogger(__name__)


class QrScanController(http.Controller):

    @http.route("/sb/qr/scan", type="http", auth="user",
                methods=["GET"], website=False)
    def scan_get(self, p=None, action="open", **kw):
        """HTML / redirect entry — tablet browsers."""
        if not p:
            return request.render("web.404")
        result = self._dispatch(payload=p, action=action, params=kw,
                                 source="http")
        if result.get("ok") and result.get("act_window"):
            aw = result["act_window"]
            redirect_url = f"/odoo/action-{aw['res_model']}/{aw['res_id']}"
            return request.redirect(redirect_url)
        body = (
            "<html><body style='font-family:system-ui;padding:2rem'>"
            f"<h2>QR scan: {result.get('result', 'error')}</h2>"
            f"<p>{result.get('error') or result.get('record_name','')}</p>"
            f"<pre>{json.dumps(result, indent=2)[:1000]}</pre>"
            "</body></html>"
        )
        return request.make_response(body, headers=[
            ("Content-Type", "text/html; charset=utf-8")])

    @http.route("/sb/qr/inventory/bin-scan", type="json", auth="user",
                methods=["POST"])
    def bin_scan(self, src=None, dst=None, product=None, qty=1.0, **kw):
        """Bin-scan inventory move.

        Body:
          {
            "src":      "sb://loc/<src_id>?...",
            "dst":      "sb://loc/<dst_id>?...",
            "product":  "sb://product/<product_id>?..." or int product_id,
            "qty":      float (default 1.0)
          }

        Returns: {ok, move_id, message} or {ok:false, error}.
        """
        env = request.env
        if not src or not dst:
            return {"ok": False, "error": "src + dst required"}
        if not product:
            return {"ok": False, "error": "product required"}
        Payload = env["southbrook.qr.payload"].sudo()
        try:
            src_p = Payload.parse(src)
            dst_p = Payload.parse(dst)
            if not src_p["valid_signature"] or not dst_p["valid_signature"]:
                return {"ok": False, "error": "Invalid signature on src/dst"}
            if src_p["kind"] != "loc" or dst_p["kind"] != "loc":
                return {"ok": False, "error": "src/dst must be 'loc' kind"}
            src_id = int(src_p["ident"])
            dst_id = int(dst_p["ident"])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"src/dst parse failed: {exc}"}
        # Product may be a raw id OR an sb:// payload
        if isinstance(product, str) and product.startswith("sb://"):
            try:
                p = Payload.parse(product)
                if not p["valid_signature"]:
                    return {"ok": False, "error": "Invalid signature on product"}
                product_id = int(p["ident"])
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"product parse failed: {exc}"}
        else:
            try:
                product_id = int(product)
            except (TypeError, ValueError):
                return {"ok": False, "error": "product must be int or sb:// payload"}
        try:
            move = env["stock.move"].sudo()._scan_quick_move(
                src_id, dst_id, product_id, qty=float(qty))
            return {"ok": True, "move_id": move.id,
                    "message": f"Moved {qty} of product {product_id} from {src_id} to {dst_id}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    @http.route("/sb/qr/labels", type="http", auth="user",
                methods=["GET"], website=False)
    def labels(self, model=None, ids="", size="2x4", text="1", **kw):
        """Render a print-friendly HTML page of QR labels."""
        if not model or not ids:
            return request.make_response(
                "Missing model + ids", headers=[("Content-Type", "text/plain")])
        env = request.env
        if model not in env:
            return request.make_response(
                f"Unknown model {model}", headers=[("Content-Type", "text/plain")])
        try:
            id_list = [int(i) for i in ids.split(",") if i.strip()]
        except ValueError:
            return request.make_response(
                "Bad ids", headers=[("Content-Type", "text/plain")])
        Records = env[model].browse(id_list).exists()
        if not Records:
            return request.make_response(
                "No records", headers=[("Content-Type", "text/plain")])
        include_text = text == "1"
        size_map = {
            "2x4": ("2in", "4in"),
            "4x6": ("4in", "6in"),
            "standard": ("4in", "3in"),  # 4-up on letter
        }
        h, w = size_map.get(size, ("2in", "4in"))
        cells = []
        for rec in Records:
            qr = getattr(rec, "qr_image_base64", "") or ""
            name = getattr(rec, "display_name", "") or f"id-{rec.id}"
            text_html = (
                f'<div style="font-size:11pt;font-family:system-ui;'
                f'text-align:center;padding:4px;word-break:break-all">'
                f'{name}</div>') if include_text else ""
            img_html = (
                f'<img src="data:image/png;base64,{qr}" '
                f'style="display:block;margin:0 auto;max-width:90%;'
                f'max-height:80%"/>') if qr else (
                '<div style="color:#999">no QR</div>')
            cells.append(
                f'<div style="height:{h};width:{w};border:1px dotted #ccc;'
                f'page-break-inside:avoid;display:flex;flex-direction:column;'
                f'justify-content:space-around;align-items:center;'
                f'margin:0.1in;padding:0.05in">'
                f'{img_html}{text_html}</div>'
            )
        body = (
            "<html><head><title>QR Labels</title>"
            "<style>@media print { body { margin: 0 } }</style>"
            "</head><body style='margin:0;padding:0.2in;font-family:system-ui'>"
            "<div style='display:flex;flex-wrap:wrap;gap:0'>"
            + "".join(cells) +
            "</div>"
            "<script>setTimeout(()=>window.print(), 300)</script>"
            "</body></html>"
        )
        return request.make_response(body, headers=[
            ("Content-Type", "text/html; charset=utf-8")])

    @http.route("/sb/qr/scan", type="json", auth="user", methods=["POST"])
    def scan_post(self, **kw):
        """JSON API entry — mobile + Flutter PWA."""
        payload = kw.get("payload")
        action = kw.get("action") or "open"
        params = kw.get("params") or {}
        return self._dispatch(payload=payload, action=action, params=params,
                              source="json")

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------
    def _dispatch(self, payload, action, params, source):
        env = request.env
        Log = env["southbrook.qr.scan.log"].sudo()
        log_vals = {
            "payload": (payload or "")[:500],
            "action": action,
            "source_ip": request.httprequest.remote_addr,
            "user_agent": (
                request.httprequest.headers.get("User-Agent") or "")[:255],
        }

        if not payload:
            Log.create({**log_vals, "result": "error",
                        "error_message": "Missing payload"})
            return {"ok": False, "result": "error",
                    "error": "Missing payload"}

        # Parse + verify HMAC
        try:
            parsed = env["southbrook.qr.payload"].sudo().parse(payload)
        except Exception as exc:  # noqa: BLE001
            Log.create({**log_vals, "result": "error",
                        "error_message": str(exc)[:255]})
            return {"ok": False, "result": "error", "error": str(exc)}

        log_vals.update({
            "kind": parsed["kind"],
            "ident": str(parsed["ident"]),
        })

        if not parsed["valid_signature"]:
            Log.create({**log_vals, "result": "invalid_signature",
                        "error_message": "HMAC mismatch"})
            return {"ok": False, "result": "invalid_signature",
                    "error": "Forged or tampered QR code."}

        # Resolve kind handler
        Kind = env["southbrook.qr.kind"]
        handler = Kind.resolve_kind(parsed["kind"])
        if not handler:
            Log.create({**log_vals, "result": "unknown_kind",
                        "error_message": parsed["kind"]})
            return {"ok": False, "result": "unknown_kind",
                    "error": f"No handler for kind '{parsed['kind']}'"}

        # TTL check
        ttl = getattr(handler, "_expires_in_seconds", 0) or 0
        if ttl > 0:
            age = int(time.time()) - parsed["ts"]
            if age > ttl:
                Log.create({**log_vals, "result": "expired",
                            "error_message": f"age={age}s ttl={ttl}s"})
                return {"ok": False, "result": "expired",
                        "error": f"QR expired ({age}s old, max {ttl}s)"}

        # Expose parsed ident on the request — stateless kinds
        # (e.g. 'defect') read it from there since their handler has
        # no record-id to draw from.
        try:
            request.qr_parsed_ident = parsed["ident"]
        except Exception:  # noqa: BLE001
            pass

        # Resolve record
        try:
            record = handler.get_record(parsed["ident"])
        except AccessError:
            Log.create({**log_vals, "result": "access_denied"})
            return {"ok": False, "result": "access_denied",
                    "error": "You don't have permission for that record."}
        except Exception as exc:  # noqa: BLE001
            Log.create({**log_vals, "result": "record_not_found",
                        "error_message": str(exc)[:255]})
            return {"ok": False, "result": "record_not_found",
                    "error": str(exc)}

        log_vals.update({
            "target_model": record._name,
            "target_id": record.id,
        })

        # Dispatch action
        try:
            result = handler.handle_action(record, action, params)
            Log.create({**log_vals, "result": "ok"})
            result.setdefault("ok", True)
            result.setdefault("result", "ok")
            return result
        except NotImplementedError as exc:
            Log.create({**log_vals, "result": "unknown_action",
                        "error_message": str(exc)[:255]})
            return {"ok": False, "result": "unknown_action",
                    "error": str(exc)}
        except AccessError:
            Log.create({**log_vals, "result": "access_denied"})
            return {"ok": False, "result": "access_denied",
                    "error": "Permission denied for that action."}
        except Exception as exc:  # noqa: BLE001
            Log.create({**log_vals, "result": "error",
                        "error_message": str(exc)[:255]})
            return {"ok": False, "result": "error", "error": str(exc)}
