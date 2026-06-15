# Copyright 2026 Southbrook Cabinetry
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FreeCAD Activator — Phase 3.2 CAD bridge go-live console.

Mirror of ``southbrook.gemini.activator`` for the FreeCAD bridge daemon:

  * Is ``freecad_bridge.url`` reachable on its /health endpoint?
  * Is ``freecad_bridge.enabled`` flipped to True so
    southbrook_freecad_bridge will actually POST render jobs?
  * How many MOs are stuck at ``x_cad_status='pending'``?
  * How many DXF/STEP attachments has the bridge written back so far?

``action_render_first_mo`` is the acceptance test: pick the oldest
pending MO and ask the existing render entry point to fire. If the
attachment count increments, the bridge round-trip is real.
"""

import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


FREECAD_HEALTH_TIMEOUT = 5  # seconds — never let the UI wizard hang
DEFAULT_BRIDGE_URL = "http://southbrook-freecad-bridge:8000"
CAD_MIMETYPES = (
    "application/dxf",
    "image/vnd.dxf",
    "application/x-dxf",
    "application/step",
    "application/x-step",
    "model/step",
    "model/step+zip",
)
# Existing render entry points on mrp.production in priority order.
RENDER_METHOD_CANDIDATES = (
    "action_regenerate_cad",
    "_post_cad_render_job",
    "action_render",
    "_trigger_cad_render",
)


class SouthbrookFreecadActivator(models.Model):
    """One-row console for the FreeCAD bridge go-live decision."""

    _name = "southbrook.freecad.activator"
    _description = "FreeCAD Bridge Activation Console"
    _rec_name = "url"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    url = fields.Char(
        string="Bridge URL",
        compute="_compute_url",
        inverse="_inverse_url",
        help="Mirror of ir.config_parameter `freecad_bridge.url`. "
             "Defaults to the QNAP stack hostname.",
    )
    enabled = fields.Boolean(
        string="Bridge Enabled",
        compute="_compute_enabled",
        inverse="_inverse_enabled",
        help="Mirror of ir.config_parameter `freecad_bridge.enabled`. "
             "When False, mrp.production._post_cad_render_job is a no-op.",
    )
    last_health_check_at = fields.Datetime(readonly=True)
    last_health_check_status = fields.Selection(
        selection=[
            ("ok", "OK"),
            ("error", "Error"),
            ("never", "Never Run"),
        ],
        default="never",
        readonly=True,
    )
    last_health_check_message = fields.Text(readonly=True)
    mo_pending_cad_count = fields.Integer(
        string="MOs Pending CAD",
        compute="_compute_mo_pending_cad_count",
        help="Count of mrp.production where x_cad_status='pending'. "
             "These are the candidates for the first-render acceptance test.",
    )
    rendered_attachment_count = fields.Integer(
        string="CAD Attachments",
        compute="_compute_rendered_attachment_count",
        help="Count of ir.attachment records the bridge has written "
             "back so far, filtered by DXF/STEP mimetypes.",
    )

    # ------------------------------------------------------------------
    # Computes / inverses
    # ------------------------------------------------------------------
    @api.depends_context("uid")
    def _compute_url(self):
        param = self.env["ir.config_parameter"].sudo()
        url = param.get_param("freecad_bridge.url", DEFAULT_BRIDGE_URL)
        for rec in self:
            rec.url = url

    def _inverse_url(self):
        # .sudo() needed because freecad_bridge.url is system-scoped config;
        # admin write check happens at wizard ACL.
        param = self.env["ir.config_parameter"].sudo()
        for rec in self:
            param.set_param(
                "freecad_bridge.url",
                (rec.url or DEFAULT_BRIDGE_URL).strip(),
            )

    @api.depends_context("uid")
    def _compute_enabled(self):
        param = self.env["ir.config_parameter"].sudo()
        raw = (param.get_param("freecad_bridge.enabled", "false") or "false").strip().lower()
        for rec in self:
            rec.enabled = raw == "true"

    def _inverse_enabled(self):
        param = self.env["ir.config_parameter"].sudo()
        for rec in self:
            param.set_param(
                "freecad_bridge.enabled",
                "True" if rec.enabled else "False",
            )

    @api.depends_context("uid")
    def _compute_mo_pending_cad_count(self):
        MO = self.env["mrp.production"].sudo()
        try:
            total = MO.search_count([("x_cad_status", "=", "pending")])
        except Exception as exc:  # field may not exist on a stripped DB
            _logger.warning("mrp.production.x_cad_status unavailable: %s", exc)
            total = 0
        for rec in self:
            rec.mo_pending_cad_count = total

    @api.depends_context("uid")
    def _compute_rendered_attachment_count(self):
        Attachment = self.env["ir.attachment"].sudo()
        total = Attachment.search_count([("mimetype", "in", list(CAD_MIMETYPES))])
        for rec in self:
            rec.rendered_attachment_count = total

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    @api.model
    def action_health_check(self):
        """GET {url}/health with a short timeout. Any HTTP 200 = up."""
        rec = self._get_singleton()
        param = self.env["ir.config_parameter"].sudo()
        url = (param.get_param("freecad_bridge.url", DEFAULT_BRIDGE_URL) or "").strip()
        now = fields.Datetime.now()

        if not url:
            rec.write({
                "last_health_check_at": now,
                "last_health_check_status": "error",
                "last_health_check_message": "No `freecad_bridge.url` configured.",
            })
            return self._notification(
                title=_("FreeCAD Health Check"),
                message=_("No bridge URL configured."),
                kind="warning",
            )

        endpoint = f"{url.rstrip('/')}/health"
        status = "error"
        message = ""
        try:
            resp = requests.get(endpoint, timeout=FREECAD_HEALTH_TIMEOUT)
            if resp.status_code == 200:
                status = "ok"
                # Try to parse {"status":"ok"} but any 200 = up.
                try:
                    body = resp.json()
                    message = f"200 OK — bridge replied {body!r}"
                except ValueError:
                    message = f"200 OK — bridge replied (non-JSON, {len(resp.content)} bytes)"
            else:
                message = f"HTTP {resp.status_code} — {resp.text[:500]}"
        except requests.RequestException as exc:
            _logger.warning("FreeCAD bridge health check raised: %s", exc)
            message = f"Request to {endpoint} failed: {exc}"

        rec.write({
            "last_health_check_at": now,
            "last_health_check_status": status,
            "last_health_check_message": message,
        })
        return self._notification(
            title=_("FreeCAD Health Check"),
            message=message,
            kind="success" if status == "ok" else "danger",
        )

    def action_enable(self):
        """Flip ``freecad_bridge.enabled`` to True — gated on URL + last health OK."""
        self.ensure_one()
        param = self.env["ir.config_parameter"].sudo()
        url = (param.get_param("freecad_bridge.url", "") or "").strip()
        if not url:
            raise UserError(_(
                "Cannot enable the FreeCAD bridge: no URL is configured. "
                "Set `freecad_bridge.url` first."
            ))
        if self.last_health_check_status != "ok":
            raise UserError(_(
                "Cannot enable the FreeCAD bridge: the last health check "
                "did not return OK. Run the health check first."
            ))
        param.set_param("freecad_bridge.enabled", "True")
        return True

    def action_disable(self):
        """Flip ``freecad_bridge.enabled`` back to False (safe rollback)."""
        self.env["ir.config_parameter"].sudo().set_param("freecad_bridge.enabled", "False")
        return True

    def action_render_first_mo(self):
        """Acceptance test: render the oldest pending MO end-to-end.

        Picks the oldest mrp.production where x_cad_status='pending' and
        invokes whichever render entry point the freecad_bridge addon
        already exposes (action_regenerate_cad is the current one).
        Returns a notification action describing the outcome.
        """
        self.ensure_one()
        MO = self.env["mrp.production"].sudo()
        try:
            target = MO.search(
                [("x_cad_status", "=", "pending")],
                order="create_date asc, id asc",
                limit=1,
            )
        except Exception as exc:
            return self._notification(
                title=_("Render Acceptance Test"),
                message=_("Could not query mrp.production: %s") % exc,
                kind="danger",
            )

        if not target:
            return self._notification(
                title=_("Render Acceptance Test"),
                message=_("No MO is at x_cad_status='pending' — nothing to render."),
                kind="warning",
            )

        method_name = next(
            (name for name in RENDER_METHOD_CANDIDATES if hasattr(target, name)),
            None,
        )
        if method_name is None:
            return self._notification(
                title=_("Render Acceptance Test"),
                message=_(
                    "mrp.production exposes none of %(candidates)s — the "
                    "southbrook_freecad_bridge addon may not be installed."
                ) % {"candidates": ", ".join(RENDER_METHOD_CANDIDATES)},
                kind="danger",
            )

        try:
            getattr(target, method_name)()
        except Exception as exc:
            _logger.warning(
                "FreeCAD render entry point %s raised on MO %s: %s",
                method_name, target.display_name, exc,
            )
            return self._notification(
                title=_("Render Acceptance Test"),
                message=_(
                    "MO %(name)s — render method %(method)s raised: %(exc)s"
                ) % {
                    "name": target.display_name,
                    "method": method_name,
                    "exc": exc,
                },
                kind="danger",
            )

        return self._notification(
            title=_("Render Acceptance Test"),
            message=_(
                "Render fired for MO %(name)s via %(method)s. "
                "Watch x_cad_status flip pending → rendering → done "
                "and the CAD attachment count increment."
            ) % {"name": target.display_name, "method": method_name},
            kind="success",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _get_singleton(self):
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    @staticmethod
    def _notification(title, message, kind="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": kind,
                "sticky": kind != "success",
            },
        }
