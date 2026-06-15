# Copyright 2026 Southbrook Cabinetry
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Gemini Activator — Phase 3.1 generative go-live console.

This singleton-style Model gives an admin a one-screen handle on the AI
half of the platform's "always-on" pitch:

  * Is a real ``gemini.api_key`` set?
  * Is ``gemini.use_mock`` flipped to False so southbrook.gemini.client
    will actually hit ``generativelanguage.googleapis.com``?
  * Does a real ping return 200 OK from the model endpoint?
  * How many production (non-mock) analyses has the platform produced?

It does **not** store the API key — the key lives in
``ir.config_parameter`` and is read transiently by the client. The
``api_key_present`` field reports presence only, never the value.

Companion: ``gemini.activation.wizard`` is the operator-facing form that
sets the key, flips the flag and runs the health check in one shot.
"""

import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


GEMINI_HEALTH_TIMEOUT = 10  # seconds — never let the UI wizard hang
DEFAULT_MODEL_ID = "gemini-2.5-pro"


class SouthbrookGeminiActivator(models.Model):
    """One-row console for the Gemini integration go-live decision."""

    _name = "southbrook.gemini.activator"
    _description = "Gemini Activation Console"
    _rec_name = "model_id"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    api_key_present = fields.Boolean(
        string="API Key Set",
        compute="_compute_api_key_present",
        help="True if ir.config_parameter `gemini.api_key` is non-empty. "
             "The key value itself is never exposed through this field.",
    )
    use_mock = fields.Boolean(
        string="Use Mock Responses",
        compute="_compute_use_mock",
        inverse="_inverse_use_mock",
        help="Mirror of ir.config_parameter `gemini.use_mock`. When True, "
             "southbrook.gemini.client returns canned JSON from "
             "data/mock_responses/default_kitchen.json instead of calling "
             "the live API.",
    )
    model_id = fields.Char(
        string="Model ID",
        default=DEFAULT_MODEL_ID,
        help="Gemini model name used by the health-check ping. The "
             "real client reads its own model from sb.gemini.prompt.template.",
    )
    last_health_check_at = fields.Datetime(
        string="Last Health Check",
        readonly=True,
    )
    last_health_check_status = fields.Selection(
        selection=[
            ("ok", "OK"),
            ("error", "Error"),
            ("never", "Never Run"),
        ],
        string="Last Status",
        default="never",
        readonly=True,
    )
    last_health_check_message = fields.Text(
        string="Last Health Check Message",
        readonly=True,
    )
    production_call_count = fields.Integer(
        string="Production Analyses",
        compute="_compute_production_call_count",
        help="Count of sb.kitchen.ai.analysis records. There is no "
             "`mock` flag on the analysis model in v19, so this is the "
             "total — the production cohort is whatever was produced "
             "after use_mock was flipped to False.",
    )

    # ------------------------------------------------------------------
    # Computes / inverses
    # ------------------------------------------------------------------
    @api.depends_context("uid")
    def _compute_api_key_present(self):
        param = self.env["ir.config_parameter"].sudo()
        key = (param.get_param("gemini.api_key", "") or "").strip()
        for rec in self:
            rec.api_key_present = bool(key)

    @api.depends_context("uid")
    def _compute_use_mock(self):
        param = self.env["ir.config_parameter"].sudo()
        raw = (param.get_param("gemini.use_mock", "True") or "True").strip().lower()
        for rec in self:
            rec.use_mock = raw == "true"

    def _inverse_use_mock(self):
        # .sudo() needed because gemini.use_mock is system-scoped config;
        # admin write check happens at wizard ACL.
        param = self.env["ir.config_parameter"].sudo()
        for rec in self:
            param.set_param("gemini.use_mock", "True" if rec.use_mock else "False")

    @api.depends_context("uid")
    def _compute_production_call_count(self):
        Analysis = self.env["sb.kitchen.ai.analysis"].sudo()
        total = Analysis.search_count([])
        for rec in self:
            rec.production_call_count = total

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    @api.model
    def action_set_api_key(self, key):
        """Persist the Gemini API key to ir.config_parameter.

        .sudo() needed because gemini.api_key is system-scoped config;
        admin write check happens at wizard ACL.
        """
        param = self.env["ir.config_parameter"].sudo()
        param.set_param("gemini.api_key", (key or "").strip())
        return True

    def action_enable_real_calls(self):
        """Flip ``gemini.use_mock`` to False — gated on a present key."""
        self.ensure_one()
        param = self.env["ir.config_parameter"].sudo()
        key = (param.get_param("gemini.api_key", "") or "").strip()
        if not key:
            raise UserError(_(
                "Cannot enable real Gemini calls: no API key is configured. "
                "Set `gemini.api_key` via the activation wizard first."
            ))
        param.set_param("gemini.use_mock", "False")
        return True

    def action_revert_to_mock(self):
        """Flip ``gemini.use_mock`` back to True (safe rollback)."""
        self.env["ir.config_parameter"].sudo().set_param("gemini.use_mock", "True")
        return True

    @api.model
    def action_health_check(self):
        """One-token ping to verify the configured key reaches the model.

        Writes the outcome onto the singleton row and returns a
        display_notification action so the operator gets visual feedback.
        """
        rec = self._get_singleton()
        param = self.env["ir.config_parameter"].sudo()
        key = (param.get_param("gemini.api_key", "") or "").strip()
        model_id = (rec.model_id or DEFAULT_MODEL_ID).strip()
        now = fields.Datetime.now()

        if not key:
            rec.write({
                "last_health_check_at": now,
                "last_health_check_status": "error",
                "last_health_check_message": "No `gemini.api_key` configured.",
            })
            return self._notification(
                title=_("Gemini Health Check"),
                message=_("No API key configured."),
                kind="warning",
            )

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_id}:generateContent?key={key}"
        )
        body = {
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"maxOutputTokens": 1},
        }
        status = "error"
        message = ""
        try:
            resp = requests.post(url, json=body, timeout=GEMINI_HEALTH_TIMEOUT)
            if resp.status_code == 200:
                status = "ok"
                message = "200 OK — model responded to one-token ping."
            else:
                # Strip the key out of any echoed URL before persisting.
                redacted = resp.text[:500].replace(key, "***REDACTED***")
                message = f"HTTP {resp.status_code} — {redacted}"
        except requests.RequestException as exc:
            _logger.warning("Gemini health check raised: %s", exc)
            message = f"Request failed: {exc}"

        rec.write({
            "last_health_check_at": now,
            "last_health_check_status": status,
            "last_health_check_message": message,
        })
        return self._notification(
            title=_("Gemini Health Check"),
            message=message,
            kind="success" if status == "ok" else "danger",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _get_singleton(self):
        """Return the one activator row, creating it on first access."""
        rec = self.search([], limit=1)
        if not rec:
            rec = self.create({"model_id": DEFAULT_MODEL_ID})
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
