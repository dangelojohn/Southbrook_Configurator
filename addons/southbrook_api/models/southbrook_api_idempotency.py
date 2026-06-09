# SPDX-License-Identifier: LGPL-3.0-only
"""Idempotency-Key replay safety per G6 §5.

A given (api_key_hash, idempotency_key) pair caches the response for
config_parameter `southbrook.api.idempotency_ttl_hours` (default 24).
Replays return the cached status code + body verbatim.

A garbage-collection cron deletes records past the TTL."""
import json
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookApiIdempotency(models.Model):
    _name = "southbrook.api.idempotency"
    _description = "Southbrook API Idempotency Record"
    _order = "create_date desc"

    api_key_hash = fields.Char(required=True, index=True)
    idempotency_key = fields.Char(required=True, index=True)
    status_code = fields.Integer(required=True)
    response_body = fields.Text(required=True)

    _sql_constraints = [
        ("api_idempotency_uniq",
         "unique(api_key_hash, idempotency_key)",
         "Duplicate idempotency record for this API key + key."),
    ]

    @api.model
    def _ttl_hours(self) -> int:
        param = self.env["ir.config_parameter"].sudo()
        try:
            return int(param.get_param(
                "southbrook.api.idempotency_ttl_hours", "24"))
        except (TypeError, ValueError):
            return 24

    @api.model
    def get_cached(self, api_key_hash: str, idempotency_key: str):
        """Return (status_code, response_body) for a cache hit, else None."""
        if not (api_key_hash and idempotency_key):
            return None
        record = self.sudo().search([
            ("api_key_hash", "=", api_key_hash),
            ("idempotency_key", "=", idempotency_key),
        ], limit=1)
        if not record:
            return None
        # Expired?
        cutoff = fields.Datetime.now() - timedelta(hours=self._ttl_hours())
        if record.create_date < cutoff:
            record.sudo().unlink()
            return None
        return (record.status_code, record.response_body)

    @api.model
    def stash(self, api_key_hash: str, idempotency_key: str,
              status_code: int, response_body: str):
        if not (api_key_hash and idempotency_key):
            return
        # Best-effort; concurrent writes will race the unique constraint
        # but each attempt produces the same content so the loser is OK.
        try:
            self.sudo().create({
                "api_key_hash": api_key_hash,
                "idempotency_key": idempotency_key,
                "status_code": status_code,
                "response_body": response_body,
            })
        except Exception:
            _logger.debug("Idempotency stash race (benign)", exc_info=True)
