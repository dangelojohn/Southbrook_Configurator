# SPDX-License-Identifier: LGPL-3.0-only
"""QR kind handler for tool.asset."""
from odoo import _, api, fields, models


class ToolKitQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.kit"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Tool Kit"
    _kind_name = "kit"
    _target_model = "southbrook.tool.kit"


class ToolCribQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.crib"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Tool Crib"
    _kind_name = "crib"
    _target_model = "southbrook.tool.crib"


class ToolQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.tool"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Tool Asset"
    _kind_name = "tool"
    _target_model = "southbrook.tool.asset"

    @api.model
    def handle_action(self, record, action, params):
        Usage = self.env["southbrook.tool.usage"]
        if action == "checkout":
            # Create a real usage record so auditors can query
            # tool→WO assignment + duration + return condition.
            wo_id = (params or {}).get("workorder_id")
            vals = {"tool_id": record.id}
            if wo_id:
                try:
                    vals["workorder_id"] = int(wo_id)
                except (TypeError, ValueError):
                    pass
            usage = Usage.sudo().create(vals)
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Tool checked out → %s") % usage.name,
                    "usage_id": usage.id}
        if action == "checkin":
            condition = (params or {}).get("condition")
            # Find the most recent open usage record for this tool +
            # check it in. Operator may need to specify return condition.
            open_usage = Usage.sudo().search([
                ("tool_id", "=", record.id),
                ("checked_in_at", "=", False),
            ], limit=1, order="checked_out_at desc")
            if not open_usage:
                # No open record — fall back to chatter log for the
                # weird case where someone scans checkin without prior
                # checkout.
                record.message_post(body=_(
                    "Checkin scan with no open checkout — logged by %s") %
                    self.env.user.display_name)
                return {"record_name": record.display_name,
                        "record_id": record.id, "model": self._target_model,
                        "message": _("Tool checkin (no open checkout — "
                                     "logged to chatter)")}
            open_usage.action_checkin(condition=condition)
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Tool checked in (duration: %.1f min)") %
                    open_usage.duration_min,
                    "usage_id": open_usage.id}
        return super().handle_action(record, action, params)
