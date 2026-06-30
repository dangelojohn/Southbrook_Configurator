# Copyright 2026 Southbrook Cabinetry
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""FreeCAD Activation Wizard — Phase 3.2 operator-facing form.

One screen, one button. The operator fills the bridge URL, ticks the
toggles, and the wizard runs the sequence:

  1. write ``freecad_bridge.url`` (if changed),
  2. (optional) run /health,
  3. (optional) flip ``freecad_bridge.enabled`` to True — only if the
     health check is OK,
  4. (optional) render the oldest pending MO as the acceptance test.

Each step halts on failure and reports back via notification.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


DEFAULT_BRIDGE_URL = "http://southbrook-freecad-bridge:8000"


class FreecadActivationWizard(models.TransientModel):
    """One-shot FreeCAD bridge activation."""

    _name = "freecad.activation.wizard"
    _description = "Activate FreeCAD Bridge"

    url = fields.Char(
        string="Bridge URL",
        default=DEFAULT_BRIDGE_URL,
        required=True,
        help="Will be saved to ir.config_parameter `freecad_bridge.url`. "
             "Default is the QNAP container hostname; override if you're "
             "pointing at a dev daemon.",
    )
    run_health_check = fields.Boolean(
        string="Run Health Check",
        default=True,
        help="GET {url}/health. Any HTTP 200 is taken as up.",
    )
    enable_after_check = fields.Boolean(
        string="Enable After Health Check",
        default=True,
        help="Flip ir.config_parameter `freecad_bridge.enabled` to True. "
             "Only runs if the health check returns OK (or is skipped).",
    )
    render_first_mo = fields.Boolean(
        string="Render Oldest Pending MO",
        default=False,
        help="Acceptance test: pick the oldest mrp.production with "
             "x_cad_status='pending' and invoke its render entry point. "
             "Only runs if the bridge is enabled by the end of the chain.",
    )

    def action_apply(self):
        """Apply: save URL → (health) → (enable) → (render)."""
        self.ensure_one()
        Activator = self.env["southbrook.freecad.activator"].sudo()
        activator = Activator._get_singleton()

        # 1. Save the URL.
        new_url = (self.url or DEFAULT_BRIDGE_URL).strip()
        activator.write({"url": new_url})

        summary_lines = [f"Bridge URL: {new_url}"]
        health_ok = None

        # 2. Optional health check.
        if self.run_health_check:
            Activator.action_health_check()
            activator = Activator._get_singleton()
            health_ok = activator.last_health_check_status == "ok"
            summary_lines.append(
                f"Health check: {activator.last_health_check_status.upper()} — "
                f"{(activator.last_health_check_message or '')[:200]}"
            )
            if not health_ok:
                # Halt the chain — do not enable or render against a sick bridge.
                return self._notification(
                    title=_("FreeCAD Activation"),
                    message="\n".join(summary_lines)
                            + "\nHalting: health check did not return OK.",
                    kind="danger",
                )

        # 3. Optional enable.
        if self.enable_after_check:
            try:
                activator.action_enable()
                summary_lines.append("freecad_bridge.enabled flipped to True.")
            except UserError as exc:
                summary_lines.append(f"Could not enable bridge: {exc}")
                return self._notification(
                    title=_("FreeCAD Activation"),
                    message="\n".join(summary_lines),
                    kind="danger",
                )

        # 4. Optional first-MO render.
        if self.render_first_mo:
            # Re-check enable state before firing a render — the user may
            # have left enable_after_check off.
            param = self.env["ir.config_parameter"].sudo()
            enabled = (param.get_param("freecad_bridge.enabled", "false") or "").strip().lower() == "true"
            if not enabled:
                summary_lines.append(
                    "Skipped first-MO render: bridge is still disabled."
                )
            else:
                result = activator.action_render_first_mo()
                params = (result or {}).get("params", {})
                summary_lines.append(
                    f"First-MO render: {params.get('message', 'fired')}"
                )

        return self._notification(
            title=_("FreeCAD Activation"),
            message="\n".join(summary_lines),
            kind="success",
        )

    @staticmethod
    def _notification(title, message, kind="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": kind,
                "sticky": True,
            },
        }
