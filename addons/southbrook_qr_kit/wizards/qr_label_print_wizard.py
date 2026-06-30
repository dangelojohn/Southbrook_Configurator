# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.qr.label.print.wizard — generic per-model label print.

Outputs an HTML page with QR + label text for each selected record.
Operator browser-prints to a thermal label printer (4"x6" or 2"x4").
For real Zebra ZPL printing, wire to Odoo's IoT box once available.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


LABEL_SIZES = [
    ("2x4", '2" × 4" thermal'),
    ("4x6", '4" × 6" thermal'),
    ("standard", "Standard 8.5x11 (8 per page)"),
]


class QrLabelPrintWizard(models.TransientModel):
    _name = "southbrook.qr.label.print.wizard"
    _description = "Print QR Labels Wizard"

    target_model = fields.Char(required=True, readonly=True)
    record_ids_str = fields.Char(
        help="JSON list of record ids — populated from context.")
    label_size = fields.Selection(
        LABEL_SIZES, default="2x4", required=True)
    include_label_text = fields.Boolean(
        default=True,
        help="Include record name as text below the QR.")
    record_count = fields.Integer(compute="_compute_record_count")

    def _compute_record_count(self):
        for w in self:
            ctx_ids = self.env.context.get("default_record_ids") or []
            # ctx_ids is a Command list like [(6, 0, [1,2,3])]
            ids = []
            for cmd in ctx_ids:
                if isinstance(cmd, (list, tuple)) and len(cmd) >= 3:
                    if cmd[0] in (6,):
                        ids = list(cmd[2])
                        break
            w.record_count = len(ids)

    def action_print(self):
        self.ensure_one()
        ctx_ids = self.env.context.get("default_record_ids") or []
        ids = []
        for cmd in ctx_ids:
            if isinstance(cmd, (list, tuple)) and len(cmd) >= 3:
                if cmd[0] in (6,):
                    ids = list(cmd[2])
                    break
        if not ids:
            raise UserError(_("No records selected to print."))
        # Return URL to a print-friendly page that renders the labels.
        # The page reads /sb/qr/labels endpoint which renders QR images
        # inline.
        from urllib.parse import urlencode
        qs = urlencode({
            "model": self.target_model,
            "ids": ",".join(str(i) for i in ids),
            "size": self.label_size,
            "text": "1" if self.include_label_text else "0",
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/sb/qr/labels?{qs}",
            "target": "new",
        }
