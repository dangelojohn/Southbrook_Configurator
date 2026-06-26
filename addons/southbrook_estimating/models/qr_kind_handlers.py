# SPDX-License-Identifier: LGPL-3.0-only
"""QR kind handlers for models in this addon."""
from odoo import _, api, models


class IntakeQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.intake"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Builder PO Intake"
    _kind_name = "intake"
    _target_model = "southbrook.builder.po.intake"

    @api.model
    def handle_action(self, record, action, params):
        if action == "parse":
            record.action_parse()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Intake parsed (%s lines)") % record.line_count}
        if action == "apply":
            record.action_apply()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Intake applied — SO created")}
        return super().handle_action(record, action, params)
