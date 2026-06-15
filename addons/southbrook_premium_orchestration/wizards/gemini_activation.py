# Copyright 2026 Southbrook Cabinetry
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Gemini Activation Wizard — Phase 3.1 operator-facing form.

One screen, one button. The operator pastes the API key, ticks the
"go real" and "health check" toggles, and the wizard:

  1. writes ``gemini.api_key`` to ir.config_parameter,
  2. updates the activator's ``model_id`` field,
  3. (optional) runs the live health-check ping,
  4. (optional) flips ``gemini.use_mock`` to False — but only if the
     health check is OK, or if the operator opted out of the check.

Failure at any step halts the chain and reports back via notification.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GeminiActivationWizard(models.TransientModel):
    """One-shot Gemini integration activation."""

    _name = "gemini.activation.wizard"
    _description = "Activate Gemini Integration"

    api_key = fields.Char(
        string="Gemini API Key",
        required=True,
        help="Will be saved to ir.config_parameter `gemini.api_key`. "
             "The wizard never echoes the key back — once saved, it is "
             "read only by southbrook.gemini.client.",
    )
    model_id = fields.Char(
        string="Model ID",
        default="gemini-2.5-pro",
        required=True,
        help="Persisted to southbrook.gemini.activator.model_id. The "
             "real per-call model selection still lives on "
             "sb.gemini.prompt.template — this is the health-check ping target.",
    )
    enable_real_calls = fields.Boolean(
        string="Enable Real Calls After Save",
        default=True,
        help="Flip ir.config_parameter `gemini.use_mock` to False once "
             "the key is saved. If the health check is enabled, this "
             "only happens after the check returns OK.",
    )
    run_health_check = fields.Boolean(
        string="Run Health Check After Save",
        default=True,
        help="Send a one-token ping to the configured model to verify "
             "the API key is accepted.",
    )

    def action_apply(self):
        """Apply: save key → set model → (health-check) → (enable real)."""
        self.ensure_one()
        Activator = self.env["southbrook.gemini.activator"].sudo()
        activator = Activator._get_singleton()

        # 1. Save the API key.
        Activator.action_set_api_key(self.api_key)

        # 2. Persist the model_id on the activator row.
        activator.write({"model_id": (self.model_id or "gemini-2.5-pro").strip()})

        # 3. Optional health check.
        summary_lines = ["API key saved.", f"Model: {activator.model_id}"]
        health_ok = None
        if self.run_health_check:
            Activator.action_health_check()
            # Re-read the activator since action_health_check writes to it.
            activator = Activator._get_singleton()
            health_ok = activator.last_health_check_status == "ok"
            summary_lines.append(
                f"Health check: {activator.last_health_check_status.upper()} — "
                f"{(activator.last_health_check_message or '')[:200]}"
            )

        # 4. Optional flip to real calls — only if health check passed,
        #    or if it was skipped entirely.
        if self.enable_real_calls:
            if health_ok is False:
                summary_lines.append(
                    "Skipped flipping use_mock=False because the health "
                    "check failed. Fix the key or model, re-run the wizard."
                )
            else:
                try:
                    activator.action_enable_real_calls()
                    summary_lines.append("use_mock flipped to False — real calls live.")
                except UserError as exc:
                    summary_lines.append(f"Could not enable real calls: {exc}")

        message = "\n".join(summary_lines)
        kind = "success"
        if health_ok is False:
            kind = "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Gemini Activation"),
                "message": message,
                "type": kind,
                "sticky": True,
            },
        }
