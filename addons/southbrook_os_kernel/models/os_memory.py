# SPDX-License-Identifier: LGPL-3.0-only
"""``southbrook.os.memory`` — the OS Kernel's shared key/value memory.

Spec: docs/OS_KERNEL_SPEC.md §4. Design invariants:

* Uniqueness is enforced with ``models.Constraint`` (NOT the legacy
  ``_sql_constraints``, which Odoo 19 silently ignores — see the repo-wide
  trap catalogue).
* ``recall()`` must NEVER raise: a missing key, an expired key, or a
  corrupt/non-JSON ``value_json`` all fall through to ``default``.
* ``remember()`` upserts with full-overwrite ("PUT") semantics: every call
  replaces value, source, AND ttl — re-remembering without ``ttl_hours``
  deliberately clears any previously set expiry.
* All three APIs operate via ``sudo()`` (mirroring ``os_switch.is_on``):
  the kernel memory must be usable by any calling feature regardless of the
  caller's groups — ACLs on this model gate direct UI access, not the API.
"""
import json
from datetime import timedelta

from odoo import api, fields, models


class SouthbrookOsMemory(models.Model):
    _name = "southbrook.os.memory"
    _description = "Southbrook OS Kernel — Shared Memory"
    _rec_name = "key"

    namespace = fields.Char(required=True, index=True, default="global")
    key = fields.Char(required=True, index=True)
    value_json = fields.Text()
    source = fields.Char(help="Who/what wrote this value.")
    user_id = fields.Many2one("res.users")
    # Scanned in full by the daily vacuum_expired cron — index it.
    expires_at = fields.Datetime(index=True)
    active = fields.Boolean(default=True)

    _unique_ns_key = models.Constraint(
        "unique(namespace, key)",
        "Memory key must be unique per namespace.",
    )

    @api.model
    def remember(self, namespace, key, value, source=None, ttl_hours=None):
        """Upsert ``value`` under (namespace, key). Returns the record."""
        namespace = namespace or "global"
        value_json = json.dumps(value)
        expires_at = False
        if ttl_hours:
            expires_at = fields.Datetime.now() + timedelta(hours=ttl_hours)

        # Search including inactive/expired rows so we upsert onto them
        # instead of hitting the unique(namespace, key) constraint.
        Mem = self.sudo().with_context(active_test=False)
        existing = Mem.search(
            [("namespace", "=", namespace), ("key", "=", key)], limit=1
        )
        vals = {
            "namespace": namespace,
            "key": key,
            "value_json": value_json,
            "source": source,
            "expires_at": expires_at,
            "active": True,
        }
        if existing:
            existing.write(vals)
            return existing
        return Mem.create(vals)

    @api.model
    def recall(self, namespace, key, default=None):
        """Read back the value stored under (namespace, key).

        Never raises: missing row, expired row, or corrupt JSON all fall
        through to ``default``.
        """
        namespace = namespace or "global"
        try:
            rec = self.sudo().with_context(active_test=False).search(
                [("namespace", "=", namespace), ("key", "=", key)], limit=1
            )
            if not rec:
                return default
            if rec.expires_at and rec.expires_at < fields.Datetime.now():
                return default
            if not rec.value_json:
                return default
            return json.loads(rec.value_json)
        except Exception:
            return default

    @api.model
    def vacuum_expired(self):
        """Unlink expired rows. Called by the (out-of-scope-here) cron."""
        now = fields.Datetime.now()
        expired = self.sudo().with_context(active_test=False).search(
            [("expires_at", "!=", False), ("expires_at", "<", now)]
        )
        expired.unlink()
        return True
