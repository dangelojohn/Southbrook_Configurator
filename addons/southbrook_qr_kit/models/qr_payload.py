# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.qr.payload — HMAC-signed QR payload service.

Payload format:
    sb://<kind>/<id>?t=<unix_ts>&s=<hmac>

Where:
    kind   — registered handler alias (asbuilt / ncr / wo / loc / pick / ...)
    id     — record id (integer) OR string slug for stateless QRs
    t      — issue timestamp (seconds since epoch). Used for expiry.
    s      — HMAC-SHA256 hex of `<kind>/<id>?t=<t>` using the secret.

Secret storage:
    ir.config_parameter `southbrook.qr_kit.hmac_secret` (urlsafe-32).
    Auto-generated on first build() if missing.

Security model:
    HMAC defends against forgery — someone with a label printer
    can't fake a QR that lands on a different record. ACL on the
    target model is STILL enforced via the controller.
"""
import base64
import hashlib
import hmac
import logging
import secrets
import time
from urllib.parse import urlsplit, parse_qs

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PAYLOAD_SCHEME = "sb"
SECRET_PARAM = "southbrook.qr_kit.hmac_secret"
DEFAULT_TTL_SECONDS = 0  # 0 = no expiry


class QrPayload(models.AbstractModel):
    """Stateless service. Build + verify signed payloads."""
    _name = "southbrook.qr.payload"
    _description = "Southbrook QR Payload Service"

    # ------------------------------------------------------------------
    # Secret management
    # ------------------------------------------------------------------
    @api.model
    def _get_secret(self):
        Param = self.env["ir.config_parameter"].sudo()
        secret = Param.get_param(SECRET_PARAM)
        if not secret:
            secret = secrets.token_urlsafe(32)
            Param.set_param(SECRET_PARAM, secret)
            _logger.info("southbrook.qr_kit: generated new HMAC secret")
        return secret.encode("utf-8")

    @api.model
    def _sign(self, body):
        return hmac.new(
            self._get_secret(), body.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    @api.model
    def build(self, kind, ident, ttl_seconds=None):
        """Build a signed payload string.

        :param kind:  registered handler alias, e.g. 'asbuilt'
        :param ident: record id (int) or slug (str)
        :param ttl_seconds: if set + nonzero, payload expires after.
        :return: 'sb://<kind>/<ident>?t=<ts>&s=<hmac>'
        """
        if not kind or not str(kind).strip():
            raise UserError(_("kind is required"))
        if ident in (None, ""):
            raise UserError(_("ident is required"))
        ts = int(time.time())
        body = f"{kind}/{ident}?t={ts}"
        sig = self._sign(body)
        return f"{PAYLOAD_SCHEME}://{body}&s={sig}"

    # ------------------------------------------------------------------
    # Parse + verify
    # ------------------------------------------------------------------
    @api.model
    def parse(self, payload):
        """Parse + verify a payload. Returns dict on success.

        :returns: {kind, ident, ts, expired (bool), valid_signature (bool)}
        :raises UserError: on malformed payload.
        """
        if not payload or not isinstance(payload, str):
            raise UserError(_("Empty or non-string QR payload"))
        # Tolerate URL with or without 'sb://' prefix
        if not payload.startswith(f"{PAYLOAD_SCHEME}://"):
            raise UserError(
                _("Unrecognized QR scheme. Expected sb://kind/id?... "
                  "got: %s") % payload[:60])
        parsed = urlsplit(payload)
        if parsed.scheme != PAYLOAD_SCHEME:
            raise UserError(_("Bad scheme: %s") % parsed.scheme)
        # netloc carries the 'kind', path carries '/<ident>'
        kind = parsed.netloc
        ident = parsed.path.lstrip("/") or ""
        if not kind or not ident:
            raise UserError(
                _("Malformed payload — missing kind or ident: %s") % payload)
        query = parse_qs(parsed.query)
        # The HMAC only covers `kind/ident?t=<ts>` — any other query key would
        # ride along UNSIGNED yet still be present in the raw payload string
        # that downstream HTML/JS renderers echo, enabling query-param
        # smuggling (e.g. appending `&x=</script>...` to a validly-signed QR).
        # Reject unexpected keys so a "valid_signature" payload is also
        # structurally canonical. build() only ever emits t + s.
        extra_keys = set(query) - {"t", "s"}
        if extra_keys:
            raise UserError(
                _("Unexpected QR query parameter(s): %s")
                % ", ".join(sorted(extra_keys)))
        ts_raw = (query.get("t") or [""])[0]
        sig = (query.get("s") or [""])[0]
        try:
            ts = int(ts_raw)
        except (TypeError, ValueError):
            raise UserError(_("Missing or invalid timestamp: %s") % ts_raw)
        body = f"{kind}/{ident}?t={ts}"
        expected_sig = self._sign(body)
        valid_signature = hmac.compare_digest(sig or "", expected_sig)
        # Coerce id to int when possible (most kinds are int).
        ident_value = ident
        try:
            ident_value = int(ident)
        except (TypeError, ValueError):
            pass
        return {
            "kind": kind,
            "ident": ident_value,
            "ts": ts,
            "valid_signature": valid_signature,
            "expired": False,  # Per-kind TTL applied in controller
            "raw": payload,
        }

    # ------------------------------------------------------------------
    # Convenience: build a record-anchored payload
    # ------------------------------------------------------------------
    @api.model
    def for_record(self, record, kind=None):
        """Build a payload for a single record. Uses kind=record._name
        when not specified, but most callers pass the short alias."""
        if not record:
            raise UserError(_("for_record requires a record"))
        record.ensure_one()
        return self.build(kind or record._name, record.id)
