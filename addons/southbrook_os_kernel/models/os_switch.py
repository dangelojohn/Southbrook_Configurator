# SPDX-License-Identifier: LGPL-3.0-only
"""``southbrook.os.switch`` — the OS Kernel's kill-switch registry.

Implements OS_KERNEL_SPEC.md §1. Every AI/agent/integration feature in the
platform is expected to gate itself through :meth:`is_on` before doing
anything expensive or external. ``is_on`` MUST NEVER raise — a broken switch
lookup must fail open/closed per the caller's own ``default``, never crash
the caller's transaction.

Design notes:

* Uniqueness on ``key`` is declared via ``models.Constraint`` (Odoo 19 CE
  silently ignores the legacy ``_sql_constraints`` mechanism — see the repo
  trap catalogue).
* The spec calls out that ``_rec_name = "key"`` would be wrong here: the
  human-friendly ``name`` field stays the record name (default rec_name
  behaviour, since the model already has a field literally called
  ``name``); ``key`` is shown alongside it in views but is not the display
  name. No explicit ``_rec_name`` is set — leaving it unset gives the
  correct default.
"""
from odoo import api, fields, models


class SouthbrookOsSwitch(models.Model):
    _name = "southbrook.os.switch"
    _description = "Southbrook OS Kill-Switch Registry"
    _inherit = ["mail.thread"]
    _order = "category, key"

    key = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    enabled = fields.Boolean(default=False, tracking=True)
    category = fields.Selection(
        [
            ("ai", "AI"),
            ("agent", "Agent"),
            ("integration", "Integration"),
            ("other", "Other"),
        ],
        default="other",
    )
    note = fields.Text()

    _unique_key = models.Constraint("unique(key)", "Switch key must be unique.")

    @api.model
    def is_on(self, key, default=False):
        """Return whether the switch ``key`` is enabled.

        Never raises: any lookup failure (missing key, bad type, DB hiccup)
        falls back to ``default`` rather than propagating an exception —
        callers rely on this to gate live features safely.
        """
        try:
            switch = self.sudo().search([("key", "=", key)], limit=1)
            if not switch:
                return default
            return bool(switch.enabled)
        except Exception:
            return default

    @api.model
    def set_switch(self, key, enabled, name=None):
        """Upsert helper used by seed data and tests.

        Creates the switch row if missing (using ``name`` or falling back
        to ``key`` itself), otherwise updates ``enabled`` (and ``name`` if
        provided) on the existing row.
        """
        switch = self.sudo().search([("key", "=", key)], limit=1)
        vals = {"enabled": enabled}
        if name:
            vals["name"] = name
        if switch:
            switch.write(vals)
            return switch
        vals.update({"key": key, "name": name or key})
        return self.sudo().create(vals)
