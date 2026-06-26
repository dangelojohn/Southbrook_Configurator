# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.qr.scan.log — append-only scan audit."""
from odoo import fields, models


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

    user_id = fields.Many2one(
        "res.users", string="Scanned By",
        default=lambda s: s.env.user, index=True,
    )
    kind = fields.Char(index=True)
    ident = fields.Char(string="Ident")
    action = fields.Char(default="open")
    result = fields.Selection(
        SCAN_RESULTS, required=True, index=True, default="ok")
    target_model = fields.Char()
    target_id = fields.Integer()
    error_message = fields.Char()
    payload = fields.Char(help="Raw QR payload (for forensics).")
    source_ip = fields.Char(string="Source IP")
    user_agent = fields.Char()
