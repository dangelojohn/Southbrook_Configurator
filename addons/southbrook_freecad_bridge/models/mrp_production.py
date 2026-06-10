# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.production extension — CAD-bridge surface.

Adds the three fields the FreeCAD bridge writes back via /plm/cad_callback:

  x_cad_status         — selection: pending | rendering | done | error
  x_cad_attachment_ids — many2many to ir.attachment for DXF/SVG/PDF/STEP
  x_plm_eco_id         — many2one to southbrook.eco linking the MO to the
                          PLM revision that governs its template BoM

Also exposes ``action_regenerate_cad`` and ``_post_cad_render_job`` so the
form-button + automated-on-confirm server action can drive the render
pipeline. Both are gated on the ``freecad_bridge.enabled`` system
parameter (G2a opt-in) — they no-op cleanly when the gate is off so the
codebase can ship without forcing the bridge POST on existing MOs.
"""
import json
import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


CAD_STATUS_VALUES = [
    ("pending", "Pending"),
    ("rendering", "Rendering"),
    ("done", "Done"),
    ("error", "Error"),
]

# Default URL the bridge listens on within the docker network. Override
# via ir.config_parameter `freecad_bridge.url` if the topology changes.
DEFAULT_BRIDGE_URL = "http://southbrook-freecad-bridge:8000"


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    x_cad_status = fields.Selection(
        CAD_STATUS_VALUES,
        string="CAD Status",
        default="pending",
        tracking=True,
        help="Lifecycle of the FreeCAD render artifacts for this MO. "
             "Set by the bridge callback after a render completes.",
    )
    x_cad_attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        relation="mrp_production_cad_attachment_rel",
        column1="production_id",
        column2="attachment_id",
        string="CAD Artifacts",
        help="DXF (per panel), SVG/PDF shop drawing, STEP AP214 assembly. "
             "Written by the bridge via XML-RPC after a successful render.",
    )
    x_plm_eco_id = fields.Many2one(
        comodel_name="southbrook.eco",
        string="Governing ECO",
        ondelete="restrict",
        help="The PLM Engineering Change Order whose approved revision "
             "of the template BoM this MO was built against.",
    )

    # ──────────────────────────────────────────────────────────────────
    # G2a gate
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _g2a_enabled(env) -> bool:
        """Read the system param. Anything other than the strings
        ``true`` / ``1`` / ``yes`` (case-insensitive) means OFF."""
        val = env["ir.config_parameter"].sudo().get_param(
            "freecad_bridge.enabled", "false")
        return str(val).strip().lower() in {"true", "1", "yes"}

    # ──────────────────────────────────────────────────────────────────
    # Bridge POST
    # ──────────────────────────────────────────────────────────────────
    def _spec_for_bridge(self) -> dict:
        """Build the render-spec payload the bridge expects.

        Reads the cabinet family + envelope from the MO's product
        template (Phase 1 mapping); a future Module-2 enhancement
        will swap in the configurator's per-MO spec when available.
        """
        self.ensure_one()
        tmpl = self.product_id.product_tmpl_id
        family = getattr(tmpl, "x_cabinet_family", None) or "base"
        # Sensible defaults so a missing template attribute doesn't
        # break the POST.
        dims = {
            "width_mm":  float(getattr(tmpl, "x_default_width_mm", 600.0)),
            "height_mm": float(getattr(tmpl, "x_default_height_mm", 720.0)),
            "depth_mm":  float(getattr(tmpl, "x_default_depth_mm", 580.0)),
        }
        return {
            "production_id": self.id,
            "dimensions": dims,
            "family": family,
            "door_count": int(getattr(tmpl, "x_default_door_count", 1)),
            "output_dir": f"/srv/output/mo/{self.id}",
        }

    def _post_cad_render_job(self):
        """POST the render spec to the bridge. Used by both the form
        button and the on-confirm server action. Returns True if the
        bridge accepted the job, False otherwise. Never raises — failures
        flip ``x_cad_status`` to error and log."""
        self.ensure_one()
        if not self._g2a_enabled(self.env):
            _logger.info(
                "freecad_bridge.enabled is off — skipping render POST for MO %s",
                self.name)
            return False
        param = self.env["ir.config_parameter"].sudo()
        url = param.get_param("freecad_bridge.url", DEFAULT_BRIDGE_URL)
        secret = param.get_param("freecad_bridge.secret", "")
        try:
            resp = requests.post(
                f"{url.rstrip('/')}/render",
                json=self._spec_for_bridge(),
                headers={"X-Bridge-Secret": secret} if secret else {},
                timeout=10,
            )
            if 200 <= resp.status_code < 300:
                self.write({"x_cad_status": "rendering"})
                self.message_post(
                    body=_("CAD render job posted to bridge (HTTP %s).")
                    % resp.status_code,
                    subtype_xmlid="mail.mt_log_note",
                )
                return True
            _logger.warning(
                "FreeCAD bridge rejected render request for MO %s: HTTP %s — %s",
                self.name, resp.status_code, resp.text[:500])
            self._record_cad_error(
                f"Bridge HTTP {resp.status_code}: {resp.text[:200]}")
            return False
        except requests.RequestException as exc:
            _logger.exception(
                "FreeCAD bridge POST failed for MO %s", self.name)
            self._record_cad_error(str(exc))
            return False

    def _record_cad_error(self, msg: str) -> None:
        self.ensure_one()
        self.write({"x_cad_status": "error"})
        self.message_post(
            body=_("CAD render request failed: %s") % msg,
            subtype_xmlid="mail.mt_log_note",
        )

    # ──────────────────────────────────────────────────────────────────
    # User-facing actions
    # ──────────────────────────────────────────────────────────────────
    def action_regenerate_cad(self):
        """Form-button entry point. Re-POSTs the render job and flips
        status. Raises if the bridge gate is off — surfaces a clear
        message rather than silently no-op'ing on user click."""
        for rec in self:
            if not rec._g2a_enabled(rec.env):
                raise UserError(_(
                    "FreeCAD bridge is disabled. Ask an administrator "
                    "to set the `freecad_bridge.enabled` system parameter "
                    "to True before regenerating CAD for this MO."))
            rec._post_cad_render_job()
        return True

    # ──────────────────────────────────────────────────────────────────
    # MO confirm hook
    # ──────────────────────────────────────────────────────────────────
    def action_confirm(self):
        result = super().action_confirm()
        # Fire the bridge POST after MO is confirmed. No-op when G2a is
        # off — so installing this addon stays safe even on stacks where
        # the bridge service isn't running.
        for rec in self:
            if rec._g2a_enabled(rec.env):
                try:
                    rec._post_cad_render_job()
                except Exception:  # noqa: BLE001
                    _logger.exception(
                        "freecad_bridge POST raised post-confirm for MO %s",
                        rec.name)
        return result
