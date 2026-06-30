# SPDX-License-Identifier: LGPL-3.0-only
"""One row per label print attempt (queued/ok/error)."""
from odoo import fields, models


class SouthbrookIntegrationsIotLabelLog(models.Model):
    _name = "southbrook.integrations.iot_label_log"
    _description = "IoT Label Print Log"
    _order = "create_date desc, id desc"

    printer_id = fields.Many2one(
        "southbrook.integrations.iot_label_printer",
        ondelete="set null",
        index=True,
    )
    record_ref = fields.Reference(
        selection=[
            ("stock.picking", "Stock Picking"),
            ("mrp.production", "Manufacturing Order"),
        ],
        string="Source Record",
    )
    zpl_payload = fields.Text()
    printed_at = fields.Datetime(default=fields.Datetime.now)
    status = fields.Selection(
        [
            ("queued", "Queued"),
            ("ok", "OK"),
            ("error", "Error"),
        ],
        default="queued",
        index=True,
    )
