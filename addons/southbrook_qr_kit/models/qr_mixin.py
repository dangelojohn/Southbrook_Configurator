# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.qr.mixin — add `qr_payload` + `qr_image_base64` to any model.

Usage:

    class Asbuilt(models.Model):
        _name = "southbrook.asbuilt"
        _inherit = ["southbrook.asbuilt", "southbrook.qr.mixin"]
        _qr_kind = "asbuilt"   # ← set this; matches the registered handler

    # the mixin then provides:
    #   qr_payload (Char, computed): "sb://asbuilt/123?t=...&s=..."
    #   qr_image_base64 (Char, computed): base64 PNG of the QR
    #   action_print_qr_label (button)

If `_qr_kind` isn't set, the mixin uses `_name` verbatim (slower scan
URLs but works).

This pattern keeps qr field declarations OUT of every model file —
just inherit the mixin.
"""
import base64
import io

from odoo import api, fields, models


class QrMixin(models.AbstractModel):
    _name = "southbrook.qr.mixin"
    _description = "Southbrook QR Mixin"

    # Subclasses override:
    _qr_kind = None  # short alias; defaults to _name when None

    qr_payload = fields.Char(
        string="QR Payload",
        compute="_compute_qr_payload",
        store=False,
        help="The signed sb://... URL the QR encodes.",
    )
    qr_image_base64 = fields.Char(
        string="QR (PNG base64)",
        compute="_compute_qr_image_base64",
        store=False,
        help="Base64 PNG. Embed via "
             "img src='data:image/png;base64,#{qr_image_base64}'.",
    )

    def _effective_qr_kind(self):
        self.ensure_one()
        return getattr(self, "_qr_kind", None) or self._name

    @api.depends_context("uid")
    def _compute_qr_payload(self):
        Payload = self.env["southbrook.qr.payload"].sudo()
        for rec in self:
            try:
                rec.qr_payload = Payload.build(
                    rec._effective_qr_kind(), rec.id)
            except Exception:  # noqa: BLE001
                rec.qr_payload = ""

    @api.depends("qr_payload")
    def _compute_qr_image_base64(self):
        for rec in self:
            payload = rec.qr_payload or ""
            if not payload:
                rec.qr_image_base64 = ""
                continue
            try:
                import qrcode
            except ImportError:
                rec.qr_image_base64 = ""
                continue
            try:
                img = qrcode.make(payload, box_size=4, border=2)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                rec.qr_image_base64 = base64.b64encode(
                    buf.getvalue()).decode("ascii")
            except Exception:  # noqa: BLE001
                rec.qr_image_base64 = ""

    def action_print_qr_label(self):
        """Open the print wizard pre-targeted at this record."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Print QR Label",
            "res_model": "southbrook.qr.label.print.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_target_model": self._name,
                "default_record_ids": [(6, 0, [self.id])],
            },
        }
