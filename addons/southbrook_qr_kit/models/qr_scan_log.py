# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.qr.scan.log — append-only scan audit.

W035 (R8.14, 2026-06-27) — `employee_id` records the *actual* operator
behind the scan, resolved via `hr.employee.pin` and held in the session
as `sbk_operator_employee_id`. `user_id` continues to record the kiosk
session user (typically a shared tablet account). The two may differ;
forensics rely on having both.
"""
from datetime import timedelta

from odoo import api, fields, models

DEFAULT_RETENTION_DAYS = 180
PRUNE_CHUNK = 5000


SCAN_RESULTS = [
    ("ok", "OK"),
    ("invalid_signature", "Invalid Signature"),
    ("expired", "Expired"),
    ("unknown_kind", "Unknown Kind"),
    ("record_not_found", "Record Not Found"),
    ("access_denied", "Access Denied"),
    ("unknown_action", "Unknown Action"),
    ("error", "Error"),
]


class QrScanLog(models.Model):
    _name = "southbrook.qr.scan.log"
    _description = "Southbrook QR Scan Log"
    _order = "create_date desc, id desc"

    # High-volume append-only log: index create_date (the _order key AND the
    # default "Last 24h" search filter) — the ORM does not auto-index it.
    create_date = fields.Datetime(index=True)
    user_id = fields.Many2one(
        "res.users", string="Scanned By (Session)",
        default=lambda s: s.env.user, index=True,
        help="The Odoo session user — typically a shared tablet kiosk "
             "account. For per-operator credit see Employee.",
    )
    # W035 (R8.14): credits the real human operator behind the scan.
    # Resolved from `hr.employee.pin` via /sb/qr/identify; persisted
    # in `request.session['sbk_operator_employee_id']`. Falls back to
    # `env.user.employee_id` when no PIN has been entered. May be empty
    # for unauthenticated public scans (POD, etc).
    employee_id = fields.Many2one(
        "hr.employee", string="Operator", index=True,
        help="Resolved from the operator's hr.employee.pin entered at "
             "the tablet. Null on public/unauthenticated scans.",
    )
    kind = fields.Char(index=True)
    ident = fields.Char(string="Ident")
    action = fields.Char(default="open")
    result = fields.Selection(
        SCAN_RESULTS, required=True, index=True, default="ok")
    # The (target_model, target_id) pair is what "scan history of record X"
    # queries filter on (search view exposes target_model) — index both.
    target_model = fields.Char(index=True)
    target_id = fields.Integer(index=True)
    error_message = fields.Char()
    payload = fields.Char(help="Raw QR payload (for forensics).")
    source_ip = fields.Char(string="Source IP")
    user_agent = fields.Char()

    @api.model
    def autovacuum(self):
        """Prune scan-log rows older than the configured retention window.

        Append-only + one row per scan (incl. every failure result) means
        this table grows without bound. Retention (days) comes from the
        ``southbrook.qr_kit.scan_log_retention_days`` config parameter
        (default 180; <= 0 keeps rows forever). Chunked delete so a large
        backlog does not lock the table in one statement. Never raises.
        """
        try:
            days = int(
                self.env["ir.config_parameter"].sudo().get_param(
                    "southbrook.qr_kit.scan_log_retention_days",
                    DEFAULT_RETENTION_DAYS,
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
