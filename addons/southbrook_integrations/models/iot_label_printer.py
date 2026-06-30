# SPDX-License-Identifier: LGPL-3.0-only
"""Zebra ZPL label printer wiring (IoT-box delivered).

v1 ships the registry, ZPL template substitution, and a log row per print.
The real IoT-box dispatch (``print_via_iot``) is intentionally a NO-OP that
logs the rendered payload so a smoke test can run without a physical IoT
box on the lan. When ``iot_base`` lands and a real device id resolves,
swap the body of ``print_via_iot`` for the IoT-box HTTP call.
"""
import logging
import re

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ${var} or {var} substitutable - we accept both styles so demo templates
# copied from Zebra docs (which use {var}) work without re-editing.
_VAR_RE = re.compile(r"\$?\{(\w+)\}")


class SouthbrookIntegrationsIotLabelPrinter(models.Model):
    _name = "southbrook.integrations.iot_label_printer"
    _description = "IoT Label Printer (Zebra ZPL)"
    _order = "name"

    name = fields.Char(required=True)
    iot_device_identifier = fields.Char(
        help="IoT-box device identifier (matches `iot.device.identifier` "
             "when iot_base is installed).",
    )
    zpl_template = fields.Text(
        required=True,
        help="ZPL II template with ${var} or {var} placeholders. "
             "Substituted from the record passed to render_zpl().",
    )
    model_target = fields.Selection(
        [
            ("stock.picking", "Stock Picking"),
            ("mrp.production", "Manufacturing Order"),
            ("southbrook.production.package", "Production Package"),
        ],
        required=True,
        default="stock.picking",
        help="Record kind that triggers this printer.",
    )
    enabled = fields.Boolean(default=True)

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        "Printer name must be unique.",
    )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def render_zpl(self, record):
        """Substitute ${var}/{var} placeholders against ``record``'s fields.

        Unknown placeholders render as the empty string (intentional - a
        zebra template with `{lot}` for an MO that has no lot should not
        crash the print; the carton just gets an empty lot box).
        """
        self.ensure_one()
        if not self.zpl_template:
            raise UserError(_("Printer '%s' has no ZPL template.") % self.name)

        def _resolve(match):
            key = match.group(1)
            # Tuple-fallback chain: explicit attribute on the record, then
            # the record's display_name for sensible defaults.
            if hasattr(record, key):
                val = getattr(record, key)
                if hasattr(val, "display_name"):
                    return str(val.display_name or "")
                return str(val or "")
            return ""

        return _VAR_RE.sub(_resolve, self.zpl_template)

    def print_via_iot(self, zpl):
        """Dispatch the rendered ZPL via the IoT box.

        v1 NO-OP: writes a row to ``iot_label_log`` and logs. The real call
        will POST to ``iot_box_url/hw_proxy/default_printer_action`` with
        the ZPL payload once an IoT box is paired.
        """
        self.ensure_one()
        Log = self.env["southbrook.integrations.iot_label_log"].sudo()
        log = Log.create({
            "printer_id": self.id,
            "zpl_payload": zpl,
            "status": "queued",
        })
        _logger.info("ZPL queued for printer %s (%s bytes)", self.name, len(zpl))
        return log
