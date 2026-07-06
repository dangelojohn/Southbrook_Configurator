# SPDX-License-Identifier: LGPL-3.0-only
"""Hermes HTTP client.

This is a plain Python helper — NOT an Odoo model. It reads its API
key and endpoint from ir.config_parameter at every call (so a rotation
in Settings takes effect immediately, with no addon restart).

Security contract for callers:
  * Never serialize self._api_key into any user-visible field, log
    line, exception message, or chatter post.
  * Treat every value in the returned dict as untrusted external
    content. NEVER eval() or exec() it. HTML-sanitize anything that
    will be written to a Html field (the wizard already does this for
    long_description).
  * The validator below only checks the top-level shape — downstream
    code must still defensively .get() each nested key.

Demo/mock mode:
  * Controlled by ``southbrook_hermes_bom.demo_mode`` (ir.config_parameter,
    default "False"). When truthy, research() short-circuits BEFORE the
    api_key gate and before `requests` is even imported — demo mode must
    work offline, with no key configured, and even if the `requests`
    package is missing entirely. See _demo_response() below.
  * Demo mode NEVER touches the network. Production behaviour (key gate,
    real HTTP call) is completely unchanged when demo mode is off.
"""
import json
import logging

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 120
REQUIRED_TOP_LEVEL_KEYS = ("product_enrichment", "bom", "audit")

# Values that count as "on" for southbrook_hermes_bom.demo_mode. Kept
# permissive (any of the common truthy spellings a human might type into
# System Parameters) since this is an ops toggle, not user input.
_TRUTHY_STRINGS = ("1", "true", "yes", "on")

# Deterministic demo fixtures — see _demo_response().
_DEMO_MANUFACTURER = "Southbrook Cabinetry (demo)"
_DEMO_SOURCE_URL = "https://demo.local/hermes/mock"
# Demo/mock output is, by definition, NOT real research — it must read as
# low-confidence so the wizard's HIGH_CONFIDENCE_THRESHOLD guard refuses to
# overwrite any existing product-master value with it. (Was 0.9, which
# defeated the guard and let "[DEMO] Mock enrichment..." permanently
# overwrite description_sale — leaking onto customer quotes. See L3 fix
# 2026-07-06 and the customer-visible-field skip in hermes_wizard.py.)
_DEMO_CONFIDENCE = 0.3
_DEMO_BOM_QTYS = (1.0, 2.0, 1.0)


class HermesService:
    """Stateless dispatch helper around the Hermes /research endpoint."""

    def __init__(self, env):
        self.env = env
        self._api_key = None
        self._endpoint = None

    def _load_config(self):
        ICP = self.env["ir.config_parameter"].sudo()
        self._api_key = ICP.get_param("southbrook_hermes_bom.api_key", "")
        self._endpoint = ICP.get_param(
            "southbrook_hermes_bom.endpoint",
            "https://api.hermes.example.com/v1/research",
        )
        if not self._api_key:
            raise UserError(_(
                "Hermes API key is not configured. Go to "
                "Settings → Technical → System Parameters and set "
                "'southbrook_hermes_bom.api_key' before running research."
            ))

    @staticmethod
    def is_demo_mode(env):
        """True when southbrook_hermes_bom.demo_mode is set to a truthy
        value. Default is False (production, fail-closed) — this param
        must be explicitly opted into for offline/demo testing.

        Static so the wizard's `hermes_available` compute can share ONE
        source of truth with the service's actual gate (otherwise the UI
        'is Hermes runnable' hint could silently diverge from what
        research() really does)."""
        raw = env["ir.config_parameter"].sudo().get_param(
            "southbrook_hermes_bom.demo_mode", "False")
        return str(raw).strip().lower() in _TRUTHY_STRINGS

    def _is_demo_mode(self):
        return self.is_demo_mode(self.env)

    def research(self, payload):
        """Call Hermes /research and return the validated response dict.

        :param dict payload: structured product context
        :returns: parsed JSON response
        :raises UserError: on transport, timeout, JSON, or shape errors
        """
        if self._is_demo_mode():
            # Deliberately BEFORE _load_config()/the api_key gate and
            # before `requests` is imported — demo mode must work with
            # no key configured and even if `requests` isn't installed.
            return self._demo_response(payload)
        self._load_config()
        # Import locally so a missing `requests` install only breaks
        # this code path, not the whole module load.
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise UserError(_(
                "Python `requests` is not installed in the Odoo "
                "environment — install it before using Hermes."
            )) from exc

        headers = {
            "Authorization": "Bearer %s" % self._api_key,
            "Content-Type": "application/json",
            "User-Agent": "southbrook_hermes_bom/19.0.1.0.0",
        }
        try:
            resp = requests.post(
                self._endpoint,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout as exc:
            _logger.error(
                "Hermes timeout after %ss against %s",
                REQUEST_TIMEOUT_SECONDS, self._endpoint,
            )
            raise UserError(_(
                "Hermes API timed out after %d seconds. Please retry."
            ) % REQUEST_TIMEOUT_SECONDS) from exc
        except requests.exceptions.RequestException as exc:
            # str(exc) may include the endpoint URL; never include the
            # Authorization header content. requests doesn't put it in
            # the str() form of a RequestException, so this is fine.
            _logger.error("Hermes transport error: %s", exc)
            raise UserError(_("Hermes API error: %s") % exc) from exc

        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise UserError(_(
                "Hermes returned a non-JSON response."
            )) from exc

        self._validate_response(data)
        return data

    def _validate_response(self, data):
        """Top-level shape check. Detailed schema validation is the
        wizard's responsibility because it knows which fields are
        load-bearing for the apply step."""
        if not isinstance(data, dict):
            raise UserError(_(
                "Hermes response was not a JSON object."
            ))
        missing = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in data]
        if missing:
            raise UserError(_(
                "Hermes response is missing required section(s): %s. "
                "Got keys: %s"
            ) % (
                ", ".join(missing),
                ", ".join(sorted(data.keys())),
            ))

    def _demo_response(self, payload):
        """Deterministic, offline stand-in for a real Hermes response.

        Pure — only reads (the component lookup below) — never writes
        anything. Product-specific (keyed off `payload`) so a reviewer
        exercising the wizard in demo mode still sees plausible,
        distinguishable content per product, but the exact same payload
        always yields the exact same response (no randomness, no clock
        reads) so tests can assert on it.

        Every enrichment text field explicitly says DEMO/MOCK so no one
        downstream mistakes this for real Hermes research.
        """
        product_name = payload.get("product_name") or "Unnamed Product"
        internal_reference = payload.get("internal_reference") or ""
        pn = internal_reference or "DEMO-PN"
        user_notes = (payload.get("user_notes") or "").strip()

        install_notes = [{
            "text": (
                "DEMO MODE: this is a mock Hermes response generated "
                "locally for '%s' (ref: %s) — no external research was "
                "performed and no network call was made."
            ) % (product_name, pn),
        }]
        long_description = (
            "<p><strong>[DEMO/MOCK]</strong> This enrichment for "
            "<em>%s</em> (ref: %s) was generated offline by the Hermes "
            "demo responder for testing purposes. It does not reflect "
            "real product research.</p>"
        ) % (product_name, pn)
        if user_notes:
            # Prove the reviewer's notes actually flow through the demo
            # path, same as they would through the real one.
            install_notes.append({
                "text": "Reviewer notes (echoed back): %s" % user_notes,
            })
            long_description += (
                "<p>Reviewer notes considered: %s</p>" % user_notes
            )

        # Look up a handful of real, existing components so the BOM
        # build path has something to actually match against offline.
        # Read-only, deterministic ordering, hard-limited — this never
        # fabricates SKUs that won't match (an empty result is handled
        # gracefully by the wizard's BOM-apply step).
        # active=True matches _apply_bom's own product lookup (an
        # archived product would be proposed then silently dropped as
        # not_found). Exclude the product being enriched, or its own
        # variant could become a BOM line for its own BOM and Odoo's
        # mrp.bom cycle check would raise on apply.
        components = self.env["product.product"].sudo().search(
            [
                ("default_code", "!=", False),
                ("active", "=", True),
                ("product_tmpl_id", "!=", payload.get("product_template_id")),
            ],
            order="id", limit=3,
        )
        bom_lines = [
            {
                "sku": component.default_code,
                "name": component.display_name,
                "qty": _DEMO_BOM_QTYS[i % len(_DEMO_BOM_QTYS)],
            }
            for i, component in enumerate(components)
        ]

        return {
            "product_enrichment": {
                "name": "%s (Demo)" % product_name,
                "short_description": (
                    "[DEMO] Mock enrichment for '%s' — generated offline "
                    "by Hermes demo mode; no real research performed."
                ) % product_name,
                "long_description": long_description,
                "technical_description": (
                    "[DEMO MODE] Placeholder technical description for "
                    "'%s' (ref: %s), produced by "
                    "HermesService._demo_response() for offline testing. "
                    "Not real research output."
                ) % (product_name, pn),
                "manufacturer": _DEMO_MANUFACTURER,
                "manufacturer_pn": pn,
                "dimensions": [
                    {"label": "Width", "value": "600 mm"},
                    {"label": "Height", "value": "720 mm"},
                    {"label": "Depth", "value": "560 mm"},
                ],
                "specs": [
                    {"name": "Material", "value": "Demo placeholder"},
                    {"name": "Finish", "value": "Demo placeholder"},
                ],
                "install_notes": install_notes,
            },
            "bom": {
                "bom_type": "normal",
                "lines": bom_lines,
            },
            "audit": {
                "source_urls": [_DEMO_SOURCE_URL],
                "overall_confidence": _DEMO_CONFIDENCE,
            },
        }
