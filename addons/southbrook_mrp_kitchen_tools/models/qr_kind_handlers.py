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
        params = params or {}
        if action == "checkout":
            # One open usage per tool. Without this guard two operators
            # scanning the same blade both got an open usage row (the tool
            # "checked out" to two work orders at once), and because the asset
            # state was never touched the readiness gate still counted it
            # available — defeating the module's core promise.
            already = Usage.sudo().search([
                ("tool_id", "=", record.id),
                ("checked_in_at", "=", False),
            ], limit=1)
            if already:
                return {"record_name": record.display_name,
                        "record_id": record.id, "model": self._target_model,
                        "error": "already_checked_out",
                        "message": _(
                            "Tool is already checked out (%s). Check it in "
                            "before checking out again.")
                        % (already.checked_out_by.display_name or _("unknown"))}
            # Create a real usage record so auditors can query
            # tool→WO assignment + duration + return condition.
            # Attribute to the REAL scanning operator — the sudo() create
            # below would otherwise default checked_out_by to OdooBot.
            vals = {"tool_id": record.id, "checked_out_by": self.env.user.id}
            wo_id = params.get("workorder_id")
            if wo_id:
                try:
                    vals["workorder_id"] = int(wo_id)
                except (TypeError, ValueError):
                    pass
            usage = Usage.sudo().create(vals)
            # Reflect the checkout on the asset so the readiness gate stops
            # counting a physically-issued tool as available.
            record.sudo().write({
                "lifecycle_state": "checked_out",
                "current_holder_id": self.env.user.id,
            })
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Tool checked out → %s") % usage.name,
                    "usage_id": usage.id}
        if action == "checkin":
            condition = params.get("condition")
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
            # Return the asset to available + clear the holder, mirroring the
            # checkout state change (only when it was actually checked out, so
            # a maintenance state set meanwhile isn't clobbered).
            if record.lifecycle_state == "checked_out":
                record.sudo().write({
                    "lifecycle_state": "available",
                    "current_holder_id": False,
                })
            else:
                record.sudo().write({"current_holder_id": False})
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": _("Tool checked in (duration: %.1f min)") %
                    open_usage.duration_min,
                    "usage_id": open_usage.id}
        return super().handle_action(record, action, params)
