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
from odoo.tools import config

_logger = logging.getLogger(__name__)


class SouthbrookApiIdempotency(models.Model):
    _name = "southbrook.api.idempotency"
    _description = "Southbrook API Idempotency Record"
    _order = "create_date desc"

    api_key_hash = fields.Char(required=True, index=True)
    # `route_scope` was added 2026-06-15 — the cache used to be keyed
    # only on (api_key_hash, idempotency_key), which let a client that
    # re-used the same Idempotency-Key across two different POST routes
    # get the OTHER route's cached body. Defaults to '' so legacy rows
    # (pre-migration) still satisfy the unique constraint cleanly.
    route_scope = fields.Char(default="", index=True)
    idempotency_key = fields.Char(required=True, index=True)
    status_code = fields.Integer(required=True)
    response_body = fields.Text(required=True)

    # Odoo 19: models.Constraint (legacy _sql_constraints silently no-op'd).
    _api_idempotency_uniq = models.Constraint(
        'unique(api_key_hash, route_scope, idempotency_key)',
        "Duplicate idempotency record for this API key + route + key.",
    )

    @api.model
    def _ttl_hours(self) -> int:
        param = self.env["ir.config_parameter"].sudo()
        try:
            return int(param.get_param(
                "southbrook.api.idempotency_ttl_hours", "24"))
        except (TypeError, ValueError):
            return 24

    @api.model
    def get_cached(self, api_key_hash: str, idempotency_key: str,
                   route_scope: str = ""):
        """Return (status_code, response_body) for a cache hit, else None.

        `route_scope` is the request path (e.g. /api/v1/...). Passing
        the empty string preserves the pre-2026-06-15 behaviour for any
        caller that didn't get the route-scope upgrade.
        """
        if not (api_key_hash and idempotency_key):
            return None
        record = self.sudo().search([
            ("api_key_hash", "=", api_key_hash),
            ("route_scope", "=", route_scope or ""),
            ("idempotency_key", "=", idempotency_key),
        ], limit=1)
        if not record:
            return None
        cutoff = fields.Datetime.now() - timedelta(hours=self._ttl_hours())
        if record.create_date < cutoff:
            record.sudo().unlink()
            return None
        return (record.status_code, record.response_body)

    @api.model
    def stash(self, api_key_hash: str, idempotency_key: str,
              status_code: int, response_body: str,
              route_scope: str = ""):
        if not (api_key_hash and idempotency_key):
            return
        try:
            # SAVEPOINT is essential: two concurrent requests with the same
            # Idempotency-Key both miss the cache and both reach here; the
            # second create violates UNIQUE(api_key_hash, route_scope,
            # idempotency_key). Catching that IntegrityError WITHOUT a
            # savepoint leaves the PG transaction aborted ("poisoned cursor"),
            # so the request's final COMMIT fails — the client gets a 500 and
            # the handler's real work is rolled back, the opposite of
            # idempotent. The savepoint confines the rollback to this create.
            with self.env.cr.savepoint():
                self.sudo().create({
                    "api_key_hash": api_key_hash,
                    "route_scope": route_scope or "",
                    "idempotency_key": idempotency_key,
                    "status_code": status_code,
                    "response_body": response_body,
                })
        except Exception:
            _logger.debug("Idempotency stash race (benign)", exc_info=True)

    @api.model
    def _gc_expired(self):
        """Cron: delete idempotency records past the TTL. The lazy unlink in
        get_cached only removes rows that happen to be replayed — rows never
        replayed would otherwise accumulate forever (one per POST with an
        Idempotency-Key). Batched + committed to bound memory/lock size."""
        cutoff = fields.Datetime.now() - timedelta(hours=self._ttl_hours())
        batch = 1000
        total = 0
        while True:
            old = self.sudo().search(
                [("create_date", "<", cutoff)], limit=batch)
            if not old:
                break
            n = len(old)
            old.unlink()
            total += n
            if not config["test_enable"]:
                self.env.cr.commit()
            if n < batch:
                break
        if total:
            _logger.info(
                "Idempotency GC: purged %d expired records", total)
        return total
