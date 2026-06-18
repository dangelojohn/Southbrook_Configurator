# SPDX-License-Identifier: LGPL-3.0-only
"""P8 — Floor Traveler extension on sb.production.package.

Adds:
  - ``x_scan_log_json`` Text field — ordered scan events as JSON. The
    MI dashboard reads this to surface scan timestamps as work-step
    durations (the audit's "Surface scan timestamps on MI dashboard"
    acceptance bullet).
  - ``qr_payload`` computed Char — the string the QR code encodes
    ("sb-package:<id>"). Kept as its own field so a future
    rev can change the encoding without touching the QWeb template.
  - ``qr_image_base64`` computed Char — the base64 PNG the QWeb
    traveler embeds. Falls back to an empty string when the qrcode
    library isn't available so the report still renders.
  - ``record_scan(workcenter_code)`` method — appends a scan event
    to the log AND calls ``mrp.workorder.button_finish`` on the next
    work order in flow. This is the audit's load-bearing acceptance
    criterion: the existing tool-consumption debit fires *exactly
    once* per scan, via the existing path.
"""
import base64
import io
import json
import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SbProductionPackage(models.Model):
    _inherit = "sb.production.package"

    x_scan_log_json = fields.Text(
        string="Scan Log (JSON)",
        default="[]",
        copy=False,
        help="Ordered list of scan events as JSON: "
             "[{'ts': ISO timestamp, 'workcenter': code, 'wo_id': int}, ...]. "
             "Each entry is appended by the /southbrook/api/floor-traveler/scan "
             "endpoint; the MI dashboard surfaces durations from this list.",
    )
    qr_payload = fields.Char(
        compute="_compute_qr_payload",
        help="Plaintext string the floor traveler's QR code encodes. "
             "Format: 'sb-package:<id>'. Stable so external scanners "
             "can be coded against it.",
    )
    qr_image_base64 = fields.Char(
        compute="_compute_qr_image_base64",
        help="Base64 PNG of the QR code, computed from qr_payload. "
             "Empty string when the qrcode library is unavailable — "
             "the QWeb traveler degrades gracefully in that case.",
    )

    @api.depends()  # noqa: D401 — pure id derivation; recomputed lazily.
    def _compute_qr_payload(self):
        for pkg in self:
            pkg.qr_payload = "sb-package:%s" % pkg.id

    @api.depends("qr_payload")
    def _compute_qr_image_base64(self):
        try:
            import qrcode
        except ImportError:
            for pkg in self:
                pkg.qr_image_base64 = ""
            return
        for pkg in self:
            buf = io.BytesIO()
            img = qrcode.make(pkg.qr_payload or "")
            img.save(buf, format="PNG")
            pkg.qr_image_base64 = base64.b64encode(buf.getvalue()).decode("ascii")

    # ------------------------------------------------------------------
    # Scan handler
    # ------------------------------------------------------------------
    def record_scan(self, workcenter_code=None):
        """Record a scan event + advance the next work order.

        Returns the WO that was advanced, or empty when nothing was
        eligible (no-MO package, no in-flight WO, etc).

        The existing ``mrp.workorder.button_finish`` override in
        southbrook_premium_orchestration handles tool-consumption
        debit. We deliberately call ``button_finish`` so the audit's
        "no duplicate telemetry" criterion holds.
        """
        self.ensure_one()
        wo = self._sbk_next_workorder()
        if not wo:
            self._append_scan_event(workcenter_code, None)
            return self.env["mrp.workorder"]

        # Call the existing path — never duplicate the debit.
        wo.button_finish()
        logged_workcenter = (
            workcenter_code
            or wo.workcenter_id.name
            or wo.workcenter_id.display_name
            or ""
        )
        self._append_scan_event(logged_workcenter, wo.id)
        return wo

    def _sbk_next_workorder(self):
        """Resolve the next not-yet-finished work order on this
        package's MO. Returns empty when none."""
        if not self.mo_id:
            return self.env["mrp.workorder"]
        wos = self.mo_id.workorder_ids.filtered(
            lambda w: w.state in ("ready", "progress", "pending"))
        return wos.sorted(lambda w: (w.sequence or 0, w.id))[:1]

    def _append_scan_event(self, workcenter_code, wo_id):
        try:
            log = json.loads(self.x_scan_log_json or "[]")
        except (TypeError, ValueError):
            log = []
        log.append({
            "ts": fields.Datetime.to_string(fields.Datetime.now()),
            "workcenter": workcenter_code or "",
            "wo_id": wo_id,
        })
        self.x_scan_log_json = json.dumps(log)
