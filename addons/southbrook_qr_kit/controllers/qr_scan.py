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

# W035 (R8.14) — operator identity in the session.
# Session keys:
#   sbk_operator_employee_id   int  hr.employee.id resolved from PIN
#   sbk_operator_pin_at        int  unix-ts of PIN entry (rolling window)
#   sbk_operator_last_seen     int  unix-ts of last activity (timeout test)
_SESSION_KEY_EMP = "sbk_operator_employee_id"
_SESSION_KEY_AT = "sbk_operator_pin_at"
_SESSION_KEY_SEEN = "sbk_operator_last_seen"
_DEFAULT_TIMEOUT_MIN = 30


def _operator_timeout_seconds(env):
    """Read `southbrook.operator_session_timeout_min` ICP (minutes).
    Default 30 min. Clamped to [1, 24*60]."""
    Param = env["ir.config_parameter"].sudo()
    raw = Param.get_param(
        "southbrook.operator_session_timeout_min",
        str(_DEFAULT_TIMEOUT_MIN))
    try:
        mins = int(raw)
    except (TypeError, ValueError):
        mins = _DEFAULT_TIMEOUT_MIN
    mins = max(1, min(mins, 24 * 60))
    return mins * 60


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

    @http.route("/sb/qr/shipping/load-unit", type="json", auth="user",
                methods=["POST"])
    def load_unit(self, truck=None, unit=None, **kw):
        """Scan-to-load at the loading bay.

        Body:
          {
            "truck": "sb://truck/<truck_load_id>?...",
            "unit":  "sb://ship/<shipping_unit_id>?..."
          }

        Resolves both signed payloads, calls action_load_unit on the
        truck. Returns {ok, unit_name, is_extra, missing_count,
        extra_count, alert} so the loading-bay UI can flash green/red.
        """
        env = request.env
        Payload = env["southbrook.qr.payload"].sudo()
        if not truck or not unit:
            return {"ok": False, "error": "truck + unit required"}
        try:
            tp = Payload.parse(truck)
            up = Payload.parse(unit)
            if not tp["valid_signature"] or not up["valid_signature"]:
                return {"ok": False, "error": "Invalid signature"}
            if tp["kind"] != "truck" or up["kind"] != "ship":
                return {"ok": False,
                        "error": "truck must be 'truck' kind, unit 'ship' kind"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"parse: {exc}"}
        Truck = env["southbrook.truck.load"]
        rec = Truck.browse(int(tp["ident"])).exists()
        if not rec:
            return {"ok": False, "error": "Truck load not found"}
        try:
            result = rec.action_load_unit(int(up["ident"]))
            result.setdefault("ok", True)
            return result
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

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

    @http.route("/sb/qr/pod/submit", type="json", auth="public",
                methods=["POST"], csrf=False)
    def pod_submit(self, payload=None, signature=None, photo=None,
                   recipient=None, **kw):
        """Public POD submit. HMAC signature on the payload IS the
        identity check — anyone with the QR is authorized to capture
        POD for that unit. Re-verifies signature, ensures kind='ship',
        then calls action_mark_delivered with sudo().

        Returns {ok, message} on success, {ok:false, error} on fail.
        """
        if not payload:
            return {"ok": False, "error": "missing payload"}
        env = request.env
        try:
            parsed = env["southbrook.qr.payload"].sudo().parse(payload)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"parse: {exc}"}
        if not parsed["valid_signature"]:
            return {"ok": False, "error": "Invalid signature"}
        if parsed["kind"] != "ship":
            return {"ok": False, "error": "POD requires a 'ship' kind QR"}
        Unit = env["southbrook.shipping.unit"].sudo()
        unit = Unit.browse(int(parsed["ident"])).exists()
        if not unit:
            return {"ok": False, "error": "Shipping unit not found"}
        if unit.state == "delivered":
            return {"ok": False, "error":
                    "Already delivered at %s" % unit.delivered_at}
        # Capture POD via the existing model method.
        try:
            unit.action_mark_delivered(signature=signature, photo=photo)
            # Log to scan log under a public "pod_submit" path.
            try:
                # W035: also stamp employee_id when a PIN-bound
                # operator captured POD (rare — POD is public — but
                # supports the field tech workflow where the same
                # tablet handled the dispatch and the delivery).
                operator = self._get_operator_employee()
                env["southbrook.qr.scan.log"].sudo().create({
                    "kind": "ship", "ident": str(unit.id),
                    "action": "delivered", "result": "ok",
                    "target_model": "southbrook.shipping.unit",
                    "target_id": unit.id,
                    "payload": payload[:500],
                    "source_ip": request.httprequest.remote_addr,
                    "user_agent":
                        (request.httprequest.headers.get("User-Agent") or "")[:255],
                    "employee_id": operator.id if operator else False,
                })
            except Exception:  # noqa: BLE001
                pass
            return {"ok": True,
                    "message": "POD captured. Thank you, %s." %
                    (recipient or "driver")}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    @http.route("/sb/qr/pod", type="http", auth="public",
                methods=["GET"], website=False, csrf=False)
    def pod_capture(self, p=None, **kw):
        """Proof-of-delivery capture page.

        Workflow: driver scans the pallet/carton QR; the GET handler
        (above) detects kind=ship and redirects to /sb/qr/pod?p=<payload>.
        This page renders:
          - Big "Shipping unit <name>" header (parsed from the QR)
          - Recipient name field (free-text)
          - Canvas signature pad (touch + mouse)
          - Camera-capture photo input (mobile gets back camera via
            capture=environment hint)
          - "Confirm Delivery" button that POSTs to /sb/qr/scan with
            action=delivered + base64 signature + base64 photo

        Lightweight HTML + vanilla JS — no Flutter, no React, no
        third-party signature lib. Works on Safari/Chrome/Edge mobile
        + desktop. Survives the /app/ Safari Content-Length bug
        because this is an Odoo route, not Caddy-served static.
        """
        if not p:
            return request.make_response(
                "Missing ?p=<qr_payload>",
                headers=[("Content-Type", "text/plain")])
        # Parse + verify signature server-side so we don't render a
        # POD form for a forged QR.
        try:
            parsed = request.env["southbrook.qr.payload"].sudo().parse(p)
        except Exception as exc:  # noqa: BLE001
            return request.make_response(
                f"Bad QR: {exc}",
                headers=[("Content-Type", "text/plain")])
        if not parsed["valid_signature"]:
            return request.make_response(
                "Invalid QR signature — forged or tampered.",
                headers=[("Content-Type", "text/plain")])
        if parsed["kind"] != "ship":
            return request.make_response(
                f"This page only handles 'ship' kind QRs (got '{parsed['kind']}').",
                headers=[("Content-Type", "text/plain")])
        Unit = request.env["southbrook.shipping.unit"].sudo()
        unit = Unit.browse(int(parsed["ident"])).exists()
        if not unit:
            return request.make_response(
                f"Shipping unit id={parsed['ident']} not found",
                headers=[("Content-Type", "text/plain")])
        return self._render_pod_page(p, unit)

    def _render_pod_page(self, payload, unit):
        """Render the POD capture page."""
        import html as html_lib
        partner = unit.partner_id.display_name if unit.partner_id else "(no customer)"
        builder = unit.builder_unit_ref or ""
        kind_label = dict(unit._fields["kind"].selection).get(unit.kind, unit.kind)
        contents = ", ".join(unit.product_ids.mapped("name"))[:300]
        e = html_lib.escape
        body = (
            "<!DOCTYPE html><html><head>"
            "<meta charset='utf-8'/>"
            "<meta name='viewport' content='width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no'/>"
            "<title>POD — " + e(unit.name) + "</title>"
            "<style>"
            "* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }"
            "body { font-family: -apple-system, system-ui, sans-serif; margin: 0; "
            "       padding: 1rem; background: #f6f6f6; color: #222; }"
            "h1 { font-size: 1.4rem; margin: 0 0 0.5rem; }"
            ".muted { color: #666; font-size: 0.95rem; }"
            ".card { background: white; border-radius: 8px; padding: 1rem; "
            "        margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }"
            "label { display: block; font-weight: 600; margin-bottom: 0.4rem; }"
            "input, textarea { width: 100%; padding: 0.7rem; font-size: 1rem; "
            "                  border: 1px solid #ccc; border-radius: 6px; }"
            "canvas { border: 2px dashed #888; background: white; "
            "         touch-action: none; display: block; width: 100%; height: 200px; }"
            ".btn { display: block; width: 100%; padding: 1rem; font-size: 1.1rem; "
            "       font-weight: 600; border: 0; border-radius: 8px; cursor: pointer; "
            "       margin-top: 1rem; }"
            ".btn-primary { background: #2b8a3e; color: white; }"
            ".btn-primary:disabled { background: #888; cursor: not-allowed; }"
            ".btn-secondary { background: #e0e0e0; color: #222; }"
            ".sig-actions { display: flex; gap: 0.5rem; margin-top: 0.5rem; }"
            ".sig-actions button { flex: 1; padding: 0.5rem; }"
            "#status { padding: 1rem; border-radius: 8px; margin-top: 1rem; }"
            ".status-ok { background: #d4edda; color: #155724; }"
            ".status-err { background: #f8d7da; color: #721c24; }"
            "img.preview { max-width: 100%; max-height: 200px; "
            "              border-radius: 6px; margin-top: 0.5rem; }"
            "</style></head><body>"
            "<div class='card'>"
            "<h1>" + e(unit.name) + " <span class='muted'>(" + e(kind_label) + ")</span></h1>"
            "<div class='muted'>"
            "<div><strong>Customer:</strong> " + e(partner) + "</div>"
            + ("<div><strong>Builder Unit:</strong> " + e(builder) + "</div>" if builder else "")
            + ("<div><strong>Contents:</strong> " + e(contents) + "</div>" if contents else "")
            + "</div></div>"
            "<form id='pod-form' onsubmit='return submitPod(event)'>"
            "<div class='card'><label for='recipient'>Recipient Name</label>"
            "<input type='text' id='recipient' name='recipient' "
            "placeholder='Print name of person accepting delivery' required></div>"
            "<div class='card'><label>Signature</label>"
            "<canvas id='sig' width='600' height='200'></canvas>"
            "<div class='sig-actions'>"
            "<button type='button' class='btn btn-secondary' onclick='clearSig()'>Clear</button>"
            "</div></div>"
            "<div class='card'><label for='photo'>Delivery Photo</label>"
            "<input type='file' id='photo' name='photo' accept='image/*' "
            "capture='environment' onchange='previewPhoto(event)'>"
            "<img id='photo-preview' class='preview' style='display:none'/></div>"
            "<button type='submit' id='submit-btn' class='btn btn-primary'>"
            "Confirm Delivery"
            "</button>"
            "<div id='status' style='display:none'></div>"
            "</form>"
            "<script>"
            "const PAYLOAD = " + repr(payload) + ";"
            "const canvas = document.getElementById('sig');"
            "const ctx = canvas.getContext('2d');"
            # Make the canvas backing-store match its rendered size
            "function resizeCanvas() {"
            "  const ratio = window.devicePixelRatio || 1;"
            "  canvas.width = canvas.offsetWidth * ratio;"
            "  canvas.height = canvas.offsetHeight * ratio;"
            "  ctx.scale(ratio, ratio); ctx.lineWidth = 2.5;"
            "  ctx.lineCap = 'round'; ctx.strokeStyle = '#222';"
            "}"
            "resizeCanvas();"
            "let drawing = false, hasInk = false;"
            "function start(e) { drawing = true; hasInk = true;"
            "  const p = getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y);"
            "  e.preventDefault(); }"
            "function move(e) { if (!drawing) return;"
            "  const p = getPos(e); ctx.lineTo(p.x, p.y); ctx.stroke();"
            "  e.preventDefault(); }"
            "function end(e) { drawing = false; }"
            "function getPos(e) {"
            "  const r = canvas.getBoundingClientRect();"
            "  const t = e.touches && e.touches[0];"
            "  const cx = t ? t.clientX : e.clientX;"
            "  const cy = t ? t.clientY : e.clientY;"
            "  return { x: cx - r.left, y: cy - r.top }; }"
            "canvas.addEventListener('mousedown', start);"
            "canvas.addEventListener('mousemove', move);"
            "canvas.addEventListener('mouseup', end);"
            "canvas.addEventListener('mouseleave', end);"
            "canvas.addEventListener('touchstart', start);"
            "canvas.addEventListener('touchmove', move);"
            "canvas.addEventListener('touchend', end);"
            "function clearSig() {"
            "  ctx.clearRect(0, 0, canvas.width, canvas.height); hasInk = false; }"
            "function previewPhoto(e) {"
            "  const f = e.target.files[0]; if (!f) return;"
            "  const img = document.getElementById('photo-preview');"
            "  img.src = URL.createObjectURL(f); img.style.display = 'block'; }"
            "function fileToB64(file) { return new Promise((resolve) => {"
            "  const r = new FileReader();"
            "  r.onload = () => resolve(r.result.split(',')[1]);"
            "  r.readAsDataURL(file); }); }"
            "async function submitPod(e) {"
            "  e.preventDefault();"
            "  const btn = document.getElementById('submit-btn');"
            "  const status = document.getElementById('status');"
            "  if (!hasInk) { alert('Please sign first.'); return false; }"
            "  btn.disabled = true; btn.textContent = 'Submitting...';"
            "  const recipient = document.getElementById('recipient').value;"
            "  const sigB64 = canvas.toDataURL('image/png').split(',')[1];"
            "  let photoB64 = '';"
            "  const photoFile = document.getElementById('photo').files[0];"
            "  if (photoFile) { photoB64 = await fileToB64(photoFile); }"
            "  try {"
            "    const resp = await fetch('/sb/qr/pod/submit', {"
            "      method: 'POST',"
            "      headers: { 'Content-Type': 'application/json' },"
            "      body: JSON.stringify({ jsonrpc: '2.0', method: 'call',"
            "        params: { payload: PAYLOAD,"
            "          signature: sigB64, photo: photoB64,"
            "          recipient: recipient } })"
            "    });"
            "    const data = await resp.json();"
            "    const r = data.result || {};"
            "    status.style.display = 'block';"
            "    if (r.ok) { status.className = 'status-ok';"
            "      status.innerHTML = '<strong>✅ Delivered!</strong><br/>' + (r.message || '');"
            "      btn.style.display = 'none'; }"
            "    else { status.className = 'status-err';"
            "      status.innerHTML = '<strong>❌ Error:</strong> ' + (r.error || 'unknown');"
            "      btn.disabled = false; btn.textContent = 'Try Again'; }"
            "  } catch (err) {"
            "    status.style.display = 'block'; status.className = 'status-err';"
            "    status.textContent = 'Network error: ' + err;"
            "    btn.disabled = false; btn.textContent = 'Try Again';"
            "  }"
            "  return false;"
            "}"
            "</script></body></html>"
        )
        return request.make_response(body, headers=[
            ("Content-Type", "text/html; charset=utf-8")])

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
    # W035 (R8.14) — operator identity via hr.employee.pin
    # ------------------------------------------------------------------

    @http.route("/sb/qr/identify", type="json", auth="public",
                csrf=False, methods=["POST"])
    def identify_operator(self, pin=None, **kw):
        """Resolve `hr.employee` from PIN and pin the employee id into
        the session. Subsequent scans credit this employee (not the
        shared kiosk session user) via `_get_operator_employee`.

        Body:  { "pin": "1234" }
        Returns:
          ok:   {"ok": true, "employee": {"id": <id>, "name": "..."},
                 "timeout_min": <minutes>}
          fail: {"ok": false, "error": "..."}

        Security:
          - PIN never echoed back, never logged.
          - PIN must be all-digits to short-circuit user-table probes.
          - `sudo()` is used to read hr.employee (operators don't have
            HR read; PIN itself is the auth factor).
        """
        # Normalize. Accept str; reject anything that isn't digits-only
        # — Odoo's native PIN is stored as a string but is documented
        # numeric, and keeping it that way means we never PIN-match a
        # username/passphrase by accident.
        pin = (pin or "").strip()
        if not pin:
            return {"ok": False, "error": "PIN required"}
        if not pin.isdigit() or not (3 <= len(pin) <= 12):
            return {"ok": False, "error": "PIN must be 3-12 digits"}
        emp = request.env["hr.employee"].sudo().search([
            ("pin", "=", pin),
            ("active", "=", True),
        ], limit=1)
        if not emp:
            # Constant-time-ish: do NOT include hint about whether the
            # PIN exists for a deactivated employee. Single message.
            return {"ok": False, "error": "Unknown PIN"}
        now = int(time.time())
        request.session[_SESSION_KEY_EMP] = emp.id
        request.session[_SESSION_KEY_AT] = now
        request.session[_SESSION_KEY_SEEN] = now
        timeout_sec = _operator_timeout_seconds(request.env)
        return {
            "ok": True,
            "employee": {"id": emp.id, "name": emp.name},
            "timeout_min": timeout_sec // 60,
        }

    @http.route("/sb/qr/switch-operator", type="json", auth="public",
                csrf=False, methods=["POST"])
    def switch_operator(self, **kw):
        """Clear the session operator binding. The next scan reverts
        to `env.user.employee_id` fallback until a fresh PIN is entered.
        UI calls this on the explicit 'Switch Operator' button."""
        for k in (_SESSION_KEY_EMP, _SESSION_KEY_AT, _SESSION_KEY_SEEN):
            try:
                request.session.pop(k, None)
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True}

    @http.route("/sb/qr/whoami", type="json", auth="public",
                csrf=False, methods=["POST", "GET"])
    def whoami(self, **kw):
        """Return the currently-bound operator (if any). UI uses this
        on tablet load to decide whether to prompt for a PIN."""
        emp = self._get_operator_employee()
        timeout_sec = _operator_timeout_seconds(request.env)
        if not emp:
            return {"ok": True, "employee": None,
                    "timeout_min": timeout_sec // 60}
        return {
            "ok": True,
            "employee": {"id": emp.id, "name": emp.name},
            "timeout_min": timeout_sec // 60,
        }

    def _get_operator_employee(self):
        """Resolve the operator for the current request.

        Lookup order:
          1. `request.session[sbk_operator_employee_id]` (set by
             /sb/qr/identify) — but only if within the session timeout.
          2. `env.user.employee_id` — convenient fallback for desk
             users whose Odoo account already maps to an employee.
          3. Empty recordset.

        Side effect: bumps `sbk_operator_last_seen` on hit so the
        rolling timeout extends with activity.
        """
        try:
            eid = request.session.get(_SESSION_KEY_EMP)
        except Exception:  # noqa: BLE001
            eid = None
        if eid:
            seen = request.session.get(_SESSION_KEY_SEEN) or \
                request.session.get(_SESSION_KEY_AT) or 0
            now = int(time.time())
            timeout_sec = _operator_timeout_seconds(request.env)
            if now - int(seen) > timeout_sec:
                # Timed out — clear and fall through to fallback.
                for k in (_SESSION_KEY_EMP, _SESSION_KEY_AT,
                          _SESSION_KEY_SEEN):
                    try:
                        request.session.pop(k, None)
                    except Exception:  # noqa: BLE001
                        pass
            else:
                emp = request.env["hr.employee"].sudo().browse(eid)
                if emp.exists() and emp.active:
                    # Bump rolling timeout on each scan.
                    request.session[_SESSION_KEY_SEEN] = now
                    return emp
                # Stale id (employee archived) → drop.
                for k in (_SESSION_KEY_EMP, _SESSION_KEY_AT,
                          _SESSION_KEY_SEEN):
                    try:
                        request.session.pop(k, None)
                    except Exception:  # noqa: BLE001
                        pass
        # Fallback: the kiosk session user may itself have an employee.
        try:
            return request.env.user.employee_id
        except Exception:  # noqa: BLE001
            return request.env["hr.employee"]

    # ------------------------------------------------------------------
    # Core dispatch
    # ------------------------------------------------------------------
    def _dispatch(self, payload, action, params, source):
        env = request.env
        Log = env["southbrook.qr.scan.log"].sudo()
        # W035: stamp the resolved operator (may be empty for public
        # POD scans where no PIN has ever been entered).
        operator = self._get_operator_employee()
        log_vals = {
            "payload": (payload or "")[:500],
            "action": action,
            "source_ip": request.httprequest.remote_addr,
            "user_agent": (
                request.httprequest.headers.get("User-Agent") or "")[:255],
            "employee_id": operator.id if operator else False,
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
