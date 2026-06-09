# SPDX-License-Identifier: LGPL-3.0-only
"""API key issuance + verification.

Stored as a SHA-256 hash; the cleartext is shown to the user exactly
once at issuance time and never logged. Verification path computes the
hash of the incoming header and looks it up — the cleartext never lives
in the DB so a DB dump cannot impersonate users."""
import hashlib
import logging
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessDenied, AccessError

_logger = logging.getLogger(__name__)

KEY_DEFAULT_TTL_DAYS = 90


def _hash_key(cleartext: str) -> str:
    return "sha256:" + hashlib.sha256(cleartext.encode("utf-8")).hexdigest()


class SouthbrookApiKey(models.Model):
    _name = "southbrook.api.key"
    _description = "Southbrook API Key"
    _order = "create_date desc"

    user_id = fields.Many2one(
        "res.users", required=True, ondelete="cascade", index=True,
    )
    key_hash = fields.Char(required=True, index=True, copy=False)
    label = fields.Char(
        help="Free-text identifier shown in the user's key list "
             "(e.g. 'My iPhone', 'Office laptop').",
    )
    expires_at = fields.Datetime(index=True)
    last_used_at = fields.Datetime()
    revoked_at = fields.Datetime(copy=False)
    revoked_reason = fields.Char()

    _sql_constraints = [
        ("key_hash_uniq", "unique(key_hash)",
         "Two API keys cannot share the same hash."),
    ]

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------
    @api.model
    def issue_for_user(self, user, label=None, ttl_days=KEY_DEFAULT_TTL_DAYS):
        """Issue a fresh key for the given user. Returns the cleartext
        ONCE; the DB stores only the SHA-256 hash."""
        cleartext = secrets.token_hex(32)  # 64 hex chars = 256 bits
        expires_at = fields.Datetime.now() + timedelta(days=ttl_days)
        self.create({
            "user_id": user.id,
            "key_hash": _hash_key(cleartext),
            "label": label,
            "expires_at": expires_at,
        })
        return {"cleartext": cleartext, "expires_at": expires_at}

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    @api.model
    def verify(self, cleartext: str):
        """Return the user associated with the cleartext key, or raise
        AccessDenied. Stamps last_used_at as a side-effect."""
        if not cleartext:
            raise AccessDenied(_("Missing API key."))
        record = self.sudo().search([
            ("key_hash", "=", _hash_key(cleartext)),
            ("revoked_at", "=", False),
        ], limit=1)
        if not record:
            raise AccessDenied(_("Unknown API key."))
        if record.expires_at and record.expires_at < fields.Datetime.now():
            raise AccessDenied(_("API key expired."))
        # Touch last_used_at out-of-band (sudo + no recompute storm).
        record.sudo().write({"last_used_at": fields.Datetime.now()})
        return record.user_id

    def action_revoke(self, reason="user_revoked"):
        for record in self:
            record.write({
                "revoked_at": fields.Datetime.now(),
                "revoked_reason": reason,
            })
