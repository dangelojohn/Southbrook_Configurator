# SPDX-License-Identifier: LGPL-3.0-only
"""QR kind handlers for kitchen_mrp models."""
from odoo import _, api, models


class CutlistQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.cutlist"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Cut List"
    _kind_name = "cutlist"
    _target_model = "sb.cutlist"

    @api.model
    def handle_action(self, record, action, params):
        if action == "nested":
            # Allow operator/nester to mark cutlist as nested via scan
            record.write({"state": "nested"})
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Cutlist marked nested")}
        return super().handle_action(record, action, params)


class HardwarePackageQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.hwpkg"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Hardware Package"
    _kind_name = "hwpkg"
    _target_model = "sb.hardware.package"


class ProductionPackageQrKind(models.AbstractModel):
    """Routes `sb://pkg/<id>` QRs through /sb/qr/scan. The legacy
    /southbrook/api/floor-traveler/scan endpoint continues to accept
    'sb-package:<id>' for back-compat (also accepts signed pkg URLs
    starting 2026-06-26). Both paths log to southbrook.qr.scan.log."""
    _name = "southbrook.qr.kind.pkg"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Production Package"
    _kind_name = "pkg"
    _target_model = "sb.production.package"

    @api.model
    def handle_action(self, record, action, params):
        if action == "scan":
            wc = (params or {}).get("workcenter_code")
            wo = record.record_scan(workcenter_code=wc)
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "wo_id": wo.id if wo else None,
                    "wo_state": wo.state if wo else None,
                    "message": _("Package scan recorded")}
        return super().handle_action(record, action, params)
