# SPDX-License-Identifier: LGPL-3.0-only
"""``southbrook.os.ai.request`` — the OS Kernel's AI call ledger.

Implements OS_KERNEL_SPEC.md §2. Plain model (no ``mail.thread`` — this
table is expected to be high volume; one row per kernel ``run()`` call,
success or failure).

``name`` is a plain stored Char, NOT an ``@api.depends`` compute — the spec
explicitly calls out the simplest approach (fill it in ``create()``) since
the id-based format string needs the id, which does not exist yet at
compute time on a new record. This also sidesteps the "wrong field name in
@api.depends silently breaks the registry" trap entirely, by not using
compute here at all.
"""
from datetime import timedelta

from odoo import api, fields, models

PREVIEW_MAX_LEN = 2000
DEFAULT_RETENTION_DAYS = 90
PRUNE_CHUNK = 1000


class SouthbrookOsAiRequest(models.Model):
    _name = "southbrook.os.ai.request"
    _description = "Southbrook OS AI Request Ledger"
    _order = "create_date desc"

    name = fields.Char(readonly=True, copy=False)
    # High-volume ledger: index create_date (the _order key and a search
    # group-by) — Odoo does not index the magic create_date field by default.
    create_date = fields.Datetime(index=True)
    feature = fields.Char(required=True, index=True)
    provider = fields.Char()
    model_name = fields.Char()
    state = fields.Selection(
        [
            ("done", "Done"),
            ("error", "Error"),
            ("blocked", "Blocked"),
        ],
        required=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users", default=lambda self: self.env.user, index=True
    )
    source_model = fields.Char()
    source_res_id = fields.Integer()
    tokens_prompt = fields.Integer()
    tokens_completion = fields.Integer()
    cost_usd = fields.Float(digits=(12, 6))
    duration_ms = fields.Integer()
    error = fields.Text()
    prompt_preview = fields.Text()
    response_preview = fields.Text()
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )

    @staticmethod
    def _truncate(text):
        if not text:
            return text
        text = str(text)
        if len(text) > PREVIEW_MAX_LEN:
            return text[:PREVIEW_MAX_LEN]
        return text

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("prompt_preview"):
                vals["prompt_preview"] = self._truncate(vals["prompt_preview"])
            if vals.get("response_preview"):
                vals["response_preview"] = self._truncate(vals["response_preview"])
        records = super().create(vals_list)
        for rec in records:
            if not rec.name:
                rec.name = "AI-%05d · %s" % (rec.id, rec.feature or "")
        return records

    @api.model
    def autovacuum(self):
        """Prune ledger rows older than the configured retention window.

        This table grows one row per kernel ``run()`` call (success, error,
        or blocked) and has no natural upper bound, so without pruning it
        bloats monotonically. Retention (in days) comes from the
        ``os.ai.ledger_retention_days`` config parameter; a value <= 0 keeps
        rows forever (opt-out). Deletion is chunked so a large backlog does
        not delete in one oversized statement. Called by the daily
        ``ir_cron_os_kernel_prune_ledger`` cron. Never raises.
        """
        try:
            days = int(
                self.env["ir.config_parameter"].sudo().get_param(
                    "os.ai.ledger_retention_days", DEFAULT_RETENTION_DAYS
                )
                or 0
            )
        except (TypeError, ValueError):
            days = DEFAULT_RETENTION_DAYS
        if days <= 0:
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=days)
        pruned = 0
        while True:
            rows = self.sudo().search(
                [("create_date", "<", cutoff)], limit=PRUNE_CHUNK
            )
            if not rows:
                break
            pruned += len(rows)
            rows.unlink()
        return pruned
