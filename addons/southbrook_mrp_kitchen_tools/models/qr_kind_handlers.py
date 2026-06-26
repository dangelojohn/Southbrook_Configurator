# SPDX-License-Identifier: LGPL-3.0-only
"""QR kind handler for tool.asset."""
from odoo import _, api, fields, models


class ToolQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.tool"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Tool Asset"
    _kind_name = "tool"
    _target_model = "southbrook.tool.asset"

    @api.model
    def handle_action(self, record, action, params):
        if action == "checkout":
            wo_id = (params or {}).get("workorder_id")
            # Append to chatter — actual checkout-to-WO depends on
            # whether tool.asset has a usage log model. v1: log via
            # chatter; v2: dedicated tool.usage record per WO.
            record.message_post(body=_(
                "Tool checked out for WO id=%(wo)s by %(u)s") % {
                "wo": wo_id or "(no WO)",
                "u": self.env.user.display_name,
            })
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Tool checked out")}
        if action == "checkin":
            record.message_post(body=_(
                "Tool checked back in by %s") % self.env.user.display_name)
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Tool checked in")}
        return super().handle_action(record, action, params)
