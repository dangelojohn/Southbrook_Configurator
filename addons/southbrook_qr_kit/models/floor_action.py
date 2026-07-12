# SPDX-License-Identifier: LGPL-3.0-only
"""W072 (R8.3, 2026-06-27) — Public floor-action mini-framework.

Generalises the POD page pattern (`/sb/qr/pod/...`) so future no-login
floor flows (install check, temp-labor sign-in, etc.) only have to
register a kind handler — they don't have to touch the controller.

Pattern (mirrors southbrook.qr.kind):

    class InstallCheckKind(models.AbstractModel):
        _name = "southbrook.floor.action.kind.install_check"
        _inherit = "southbrook.floor.action.kind"
        _action_name = "install_check"
        _expected_qr_kind = "ship"  # which sb:// kind the QR carries
        _target_model = "southbrook.shipping.unit"

        def render_form(self, payload, record):
            ...  # return HTML string

        def handle_submit(self, payload, record, body):
            ...  # return {"ok": True, "message": "..."} | {"ok":False,"error":...}

Controller (controllers/floor_action.py) routes:

    GET  /sb/floor/<action>?p=<payload>          -> render_form
    POST /sb/floor/<action>/submit               -> handle_submit (JSON)

Signed-token gating, IP rate-limit, and scan-log append are handled by
the controller — kinds only own the action-specific HTML/logic.

Security:
  - Public auth (no login wall) — the HMAC signature on the payload IS
    the gate, same as POD.
  - csrf=False on submit; the signature replaces CSRF for this
    public surface.
  - All requests are logged to southbrook.qr.scan.log with the kind +
    action recorded (forensics + ops monitoring).
  - Bounded per-IP rate-limit (in-process ring).

Backward compat:
  The legacy /sb/qr/pod and /sb/qr/pod/submit routes still exist; this
  framework does NOT remove them. The pod kind handler delegates back
  into the same shipping-unit.action_mark_delivered call so behaviour
  is byte-equal to the legacy path.
"""
import json

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class FloorActionKind(models.AbstractModel):
    """Abstract base for public floor-action handlers.

    Subclasses set:
      * `_action_name`        URL slug, e.g. "pod", "install_check"
      * `_expected_qr_kind`   which `sb://<kind>/...` QR carries the ident
      * `_target_model`       Odoo model the ident refers to (optional;
                              some kinds may not need a backing record —
                              e.g. temp_labor_signin keys by free-text
                              partner name + signature)
      * `_allow_missing_record` True when the action can run without
                              backing record (signin-by-name kinds).
      * `_session_required`   default False; floor actions are public

    Subclasses override:
      * `render_form(payload, record)` -> HTML str
      * `handle_submit(payload, record, body)` -> dict
    """
    _name = "southbrook.floor.action.kind"
    _description = "Southbrook Floor-Action Kind (public, signed)"

    _action_name = None
    _expected_qr_kind = None
    _target_model = None
    _allow_missing_record = False

    @api.model
    def resolve_kind(self, action_name):
        """Find the registered handler for `action_name`.

        Convention: each handler's model name is
        'southbrook.floor.action.kind.<action_name>'. Returns env-bound
        instance or False.
        """
        if not action_name:
            return False
        # Allow hyphen in URL slug; map to underscore in model name.
        normalized = str(action_name).replace("-", "_").strip().lower()
        target = "southbrook.floor.action.kind.%s" % normalized
        if target in self.env:
            return self.env[target]
        return False

    @api.model
    def get_record(self, payload_parsed):
        """Resolve the backing record from a parsed sb:// payload.

        Returns the env-bound record, an empty recordset (when
        _allow_missing_record), or raises UserError.
        """
        if self._allow_missing_record and not self._target_model:
            return self.env[self._name] if self._name in self.env else False
        if not self._target_model:
            raise UserError(_(
                "Floor-action %s has no _target_model and is not "
                "marked _allow_missing_record.") % self._action_name)
        try:
            rid = int(payload_parsed["ident"])
        except (TypeError, ValueError, KeyError):
            raise UserError(_("ident must be int: %s") %
                            payload_parsed.get("ident"))
        rec = self.env[self._target_model].sudo().browse(rid).exists()
        if not rec:
            if self._allow_missing_record:
                return self.env[self._target_model]
            raise UserError(_(
                "%s id=%s not found") % (self._target_model, rid))
        return rec

    @api.model
    def render_form(self, payload, record):
        """Return an HTML body (str) for the GET request.

        Default raises NotImplementedError — every concrete kind MUST
        override (the whole point of the framework is per-action UI).
        """
        raise NotImplementedError(
            _("Kind %s does not implement render_form") % self._action_name)

    @api.model
    def handle_submit(self, payload, record, body):
        """Process the POST body and return a result dict.

        Result shape: {"ok": True, "message": "..."} on success or
        {"ok": False, "error": "..."} on failure.
        """
        raise NotImplementedError(
            _("Kind %s does not implement handle_submit") % self._action_name)


# ----------------------------------------------------------------------
# Built-in handler #1 — POD (refactored from legacy /sb/qr/pod pattern)
# ----------------------------------------------------------------------
class PodFloorKind(models.AbstractModel):
    """POD = proof of delivery.

    Behaviour is byte-equal to the legacy /sb/qr/pod & /sb/qr/pod/submit
    routes; the controller can delegate to this kind in the framework
    so both URL families produce the same audit trail.
    """
    _name = "southbrook.floor.action.kind.pod"
    _inherit = "southbrook.floor.action.kind"
    _description = "Floor Action — Proof of Delivery (POD)"
    _action_name = "pod"
    _expected_qr_kind = "ship"
    _target_model = "southbrook.shipping.unit"

    @api.model
    def render_form(self, payload, record):
        # Delegate to the legacy renderer on the controller. We import
        # lazily to avoid a circular import at module load.
        from odoo.addons.southbrook_qr_kit.controllers.qr_scan import (
            QrScanController,
        )
        ctrl = QrScanController()
        # _render_pod_page returns a full http.Response. The framework
        # controller knows how to surface that directly OR pull the
        # body out depending on caller mode.
        return ctrl._render_pod_page(payload, record)

    @api.model
    def handle_submit(self, payload, record, body):
        if record.state == "delivered":
            return {"ok": False, "error":
                    "Already delivered at %s" % record.delivered_at}
        try:
            record.action_mark_delivered(
                signature=body.get("signature"),
                photo=body.get("photo"),
            )
        except AccessError:
            return {"ok": False, "error": "Access denied."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        return {"ok": True,
                "message": "POD captured. Thank you, %s." %
                (body.get("recipient") or "driver")}


# ----------------------------------------------------------------------
# Built-in handler #2 — Install Check (site verification step)
# ----------------------------------------------------------------------
class InstallCheckFloorKind(models.AbstractModel):
    """Install check = the installer logs an on-site inspection.

    Keyed on the same shipping-unit QR the POD uses (the install crew
    scans the pallet QR on arrival at the job site). Captures: installer
    name, condition rating, photo, free-text notes.

    Stores result on the shipping unit's chatter; no new ORM model.
    """
    _name = "southbrook.floor.action.kind.install_check"
    _inherit = "southbrook.floor.action.kind"
    _description = "Floor Action — Install Site Check"
    _action_name = "install_check"
    _expected_qr_kind = "ship"
    _target_model = "southbrook.shipping.unit"

    @api.model
    def render_form(self, payload, record):
        import html as html_lib
        e = html_lib.escape
        partner_name = (
            record.partner_id.display_name if record.partner_id else "")
        body = (
            "<!DOCTYPE html><html><head>"
            "<meta charset='utf-8'/>"
            "<meta name='viewport' content='width=device-width,"
            " initial-scale=1, maximum-scale=1, user-scalable=no'/>"
            "<title>Install Check &mdash; " + e(record.name) + "</title>"
            "<style>"
            "* { box-sizing: border-box; }"
            "body { font-family: -apple-system, system-ui, sans-serif;"
            "  margin: 0; padding: 1rem; background: #f6f6f6; }"
            "h1 { font-size: 1.3rem; margin: 0 0 0.5rem; }"
            ".muted { color: #666; font-size: 0.95rem; }"
            ".card { background: white; border-radius: 8px;"
            "  padding: 1rem; margin-bottom: 1rem;"
            "  box-shadow: 0 1px 3px rgba(0,0,0,0.1); }"
            "label { display: block; font-weight: 600;"
            "  margin-bottom: 0.4rem; }"
            "input, textarea, select { width: 100%;"
            "  padding: 0.7rem; font-size: 1rem; border: 1px solid #ccc;"
            "  border-radius: 6px; }"
            ".btn { display: block; width: 100%; padding: 1rem;"
            "  font-size: 1.1rem; font-weight: 600; border: 0;"
            "  border-radius: 8px; cursor: pointer; margin-top: 1rem; }"
            ".btn-primary { background: #2b8a3e; color: white; }"
            "#status { padding: 1rem; border-radius: 8px;"
            "  margin-top: 1rem; }"
            ".status-ok { background: #d4edda; color: #155724; }"
            ".status-err { background: #f8d7da; color: #721c24; }"
            "</style></head><body>"
            "<div class='card'>"
            "<h1>Install Check &mdash; " + e(record.name) + "</h1>"
            "<div class='muted'><strong>Customer:</strong> "
            + e(partner_name) + "</div></div>"
            "<form id='ic-form' onsubmit='return submitIC(event)'>"
            "<div class='card'><label>Installer name</label>"
            "<input type='text' id='installer' required></div>"
            "<div class='card'><label>Condition on arrival</label>"
            "<select id='condition' required>"
            "<option value=''>Select...</option>"
            "<option value='ok'>OK &mdash; no damage</option>"
            "<option value='minor'>Minor damage (note below)</option>"
            "<option value='major'>Major damage (do not install)</option>"
            "</select></div>"
            "<div class='card'><label>Notes</label>"
            "<textarea id='notes' rows='3' placeholder='Optional'>"
            "</textarea></div>"
            "<button type='submit' id='submit-btn' class='btn btn-primary'>"
            "Log Install Check</button>"
            "<div id='status' style='display:none'></div>"
            "</form>"
            "<script>"
            "const PAYLOAD = " + json.dumps(payload).replace("</", "<\\/") + ";"
            "async function submitIC(e) {"
            "  e.preventDefault();"
            "  const btn = document.getElementById('submit-btn');"
            "  const status = document.getElementById('status');"
            "  btn.disabled = true; btn.textContent = 'Submitting...';"
            "  const installer = document.getElementById('installer').value;"
            "  const condition = document.getElementById('condition').value;"
            "  const notes = document.getElementById('notes').value;"
            "  try {"
            "    const resp = await fetch("
            "      '/sb/floor/install_check/submit', {"
            "      method: 'POST',"
            "      headers: { 'Content-Type': 'application/json' },"
            "      body: JSON.stringify({ jsonrpc: '2.0', method: 'call',"
            "        params: { payload: PAYLOAD,"
            "          installer: installer, condition: condition,"
            "          notes: notes } }) });"
            "    const data = await resp.json();"
            "    const r = data.result || {};"
            "    status.style.display = 'block';"
            "    if (r.ok) { status.className = 'status-ok';"
            "      status.textContent = r.message;"
            "      btn.style.display = 'none'; }"
            "    else { status.className = 'status-err';"
            "      status.textContent = r.error || 'unknown';"
            "      btn.disabled = false; btn.textContent = 'Try Again'; }"
            "  } catch (err) {"
            "    status.style.display = 'block';"
            "    status.className = 'status-err';"
            "    status.textContent = 'Network error: ' + err;"
            "    btn.disabled = false; btn.textContent = 'Try Again';"
            "  }"
            "  return false;"
            "}"
            "</script></body></html>"
        )
        return body

    @api.model
    def handle_submit(self, payload, record, body):
        installer = (body.get("installer") or "").strip()
        condition = (body.get("condition") or "").strip()
        notes = (body.get("notes") or "").strip()
        if not installer:
            return {"ok": False, "error": "Installer name required"}
        if condition not in ("ok", "minor", "major"):
            return {"ok": False, "error":
                    "condition must be one of: ok, minor, major"}
        cond_label = {
            "ok": "OK (no damage)",
            "minor": "Minor damage",
            "major": "MAJOR damage — do not install",
        }[condition]
        body_html = _(
            "<b>Install check</b> — installer: %(installer)s | "
            "condition: %(cond)s") % {
            "installer": installer, "cond": cond_label}
        if notes:
            body_html += "<br/>%s" % notes
        try:
            record.sudo().message_post(body=body_html)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "message": "Install check logged on %s. Thanks, %s." %
            (record.name, installer),
        }


# ----------------------------------------------------------------------
# Built-in handler #3 — Temp Labor Sign-in
# ----------------------------------------------------------------------
class TempLaborSigninFloorKind(models.AbstractModel):
    """Temp-labor sign-in for unbadged workers on site or in the yard.

    The QR is keyed on a stock.location (the yard / warehouse bay). The
    worker enters name + contact + arrival time; we attach the record
    to the location's chatter so the supervisor sees who showed up where.
    Falls back to a session-only log if the location has no chatter.
    """
    _name = "southbrook.floor.action.kind.temp_labor_signin"
    _inherit = "southbrook.floor.action.kind"
    _description = "Floor Action — Temp Labor Sign-in"
    _action_name = "temp_labor_signin"
    _expected_qr_kind = "loc"
    _target_model = "stock.location"

    @api.model
    def render_form(self, payload, record):
        import html as html_lib
        e = html_lib.escape
        loc_name = (record.complete_name or record.name) if record else "(site)"
        body = (
            "<!DOCTYPE html><html><head>"
            "<meta charset='utf-8'/>"
            "<meta name='viewport' content='width=device-width,"
            " initial-scale=1, maximum-scale=1, user-scalable=no'/>"
            "<title>Sign In &mdash; " + e(loc_name) + "</title>"
            "<style>"
            "body { font-family: -apple-system, system-ui, sans-serif;"
            "  margin: 0; padding: 1rem; background: #f6f6f6; }"
            "h1 { font-size: 1.3rem; margin: 0 0 0.5rem; }"
            ".muted { color: #666; font-size: 0.95rem; }"
            ".card { background: white; border-radius: 8px;"
            "  padding: 1rem; margin-bottom: 1rem;"
            "  box-shadow: 0 1px 3px rgba(0,0,0,0.1); }"
            "label { display: block; font-weight: 600;"
            "  margin-bottom: 0.4rem; }"
            "input, textarea { width: 100%; padding: 0.7rem;"
            "  font-size: 1rem; border: 1px solid #ccc;"
            "  border-radius: 6px; }"
            ".btn { display: block; width: 100%; padding: 1rem;"
            "  font-size: 1.1rem; font-weight: 600; border: 0;"
            "  border-radius: 8px; cursor: pointer; margin-top: 1rem;"
            "  background: #2b8a3e; color: white; }"
            "#status { padding: 1rem; border-radius: 8px;"
            "  margin-top: 1rem; }"
            ".status-ok { background: #d4edda; color: #155724; }"
            ".status-err { background: #f8d7da; color: #721c24; }"
            "</style></head><body>"
            "<div class='card'>"
            "<h1>Sign In &mdash; " + e(loc_name) + "</h1>"
            "<div class='muted'>Sign in for today's work at this location."
            "</div></div>"
            "<form id='tl-form' onsubmit='return submitTL(event)'>"
            "<div class='card'><label>Your full name</label>"
            "<input type='text' id='full_name' required></div>"
            "<div class='card'><label>Contact (phone or email)</label>"
            "<input type='text' id='contact' required></div>"
            "<div class='card'><label>Crew / company (optional)</label>"
            "<input type='text' id='crew'></div>"
            "<button type='submit' id='submit-btn' class='btn'>"
            "Sign In</button>"
            "<div id='status' style='display:none'></div>"
            "</form>"
            "<script>"
            "const PAYLOAD = " + json.dumps(payload).replace("</", "<\\/") + ";"
            "async function submitTL(e) {"
            "  e.preventDefault();"
            "  const btn = document.getElementById('submit-btn');"
            "  const status = document.getElementById('status');"
            "  btn.disabled = true; btn.textContent = 'Submitting...';"
            "  const full_name = document.getElementById('full_name').value;"
            "  const contact = document.getElementById('contact').value;"
            "  const crew = document.getElementById('crew').value;"
            "  try {"
            "    const resp = await fetch("
            "      '/sb/floor/temp_labor_signin/submit', {"
            "      method: 'POST',"
            "      headers: { 'Content-Type': 'application/json' },"
            "      body: JSON.stringify({ jsonrpc: '2.0', method: 'call',"
            "        params: { payload: PAYLOAD,"
            "          full_name: full_name, contact: contact,"
            "          crew: crew } }) });"
            "    const data = await resp.json();"
            "    const r = data.result || {};"
            "    status.style.display = 'block';"
            "    if (r.ok) { status.className = 'status-ok';"
            "      status.textContent = r.message;"
            "      btn.style.display = 'none'; }"
            "    else { status.className = 'status-err';"
            "      status.textContent = r.error || 'unknown';"
            "      btn.disabled = false; btn.textContent = 'Try Again'; }"
            "  } catch (err) {"
            "    status.style.display = 'block';"
            "    status.className = 'status-err';"
            "    status.textContent = 'Network error: ' + err;"
            "    btn.disabled = false; btn.textContent = 'Try Again';"
            "  }"
            "  return false;"
            "}"
            "</script></body></html>"
        )
        return body

    @api.model
    def handle_submit(self, payload, record, body):
        full_name = (body.get("full_name") or "").strip()
        contact = (body.get("contact") or "").strip()
        crew = (body.get("crew") or "").strip()
        if not full_name or not contact:
            return {"ok": False, "error":
                    "Full name and contact are required"}
        if len(full_name) > 120 or len(contact) > 120 or len(crew) > 120:
            return {"ok": False, "error":
                    "Each field must be <=120 characters"}
        body_html = _(
            "<b>Temp-labor sign-in</b> &mdash; %(n)s | %(c)s%(crew)s") % {
            "n": full_name, "c": contact,
            "crew": (" | %s" % crew) if crew else "",
        }
        # stock.location doesn't inherit mail.thread natively; fall back
        # to an admin-readable scan-log entry in that case. The
        # controller already writes the per-request scan-log row; this
        # branch upgrades it with the sign-in detail when chatter
        # IS available.
        if record and hasattr(record, "message_post"):
            try:
                record.sudo().message_post(body=body_html)
            except Exception:  # noqa: BLE001
                # No chatter on stock.location in v19 CE; the scan-log
                # row written by the framework dispatcher is the
                # canonical record.
                pass
        # The action-of-record is in the scan log; the chatter post is
        # the convenience UI. Return success either way.
        return {
            "ok": True,
            "message": "Signed in. Welcome, %s." % full_name,
        }
