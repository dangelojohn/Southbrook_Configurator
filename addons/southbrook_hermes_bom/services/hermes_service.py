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
"""
import json
import logging

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 120
REQUIRED_TOP_LEVEL_KEYS = ("product_enrichment", "bom", "audit")


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

    def research(self, payload):
        """Call Hermes /research and return the validated response dict.

        :param dict payload: structured product context
        :returns: parsed JSON response
        :raises UserError: on transport, timeout, JSON, or shape errors
        """
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
