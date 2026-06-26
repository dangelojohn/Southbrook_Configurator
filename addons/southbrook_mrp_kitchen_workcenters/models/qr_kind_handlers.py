# SPDX-License-Identifier: LGPL-3.0-only
"""QR kind handlers for models defined in this addon.

Each handler resolves a 'sb://<kind>/<id>?...' QR to a southbrook
model record and dispatches the requested action. Convention: model
name 'southbrook.qr.kind.<kind>'.

Handlers shipped here:
  asbuilt  → southbrook.asbuilt
  ncr      → southbrook.mi.check (filtered to NCR-relevant records)
  wo       → mrp.workorder
  mo       → mrp.production
  opcua    → southbrook.opcua.endpoint
  shift    → southbrook.shift.handover
"""
from odoo import _, api, models
from odoo.exceptions import UserError


class AsbuiltQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.asbuilt"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — As-Built"
    _kind_name = "asbuilt"
    _target_model = "southbrook.asbuilt"

    @api.model
    def handle_action(self, record, action, params):
        if action == "seal":
            record.action_seal()
            return {"redirect": "/odoo/action-base.action_open_view/%s" % record.id,
                    "record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model}
        return super().handle_action(record, action, params)


class NcrQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.ncr"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — NCR / QC Check"
    _kind_name = "ncr"
    _target_model = "southbrook.mi.check"

    @api.model
    def handle_action(self, record, action, params):
        if action == "rework":
            record.action_create_rework_workorder()
            return {"redirect": "/odoo/action-base.action_open_view/%s" % record.id,
                    "record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model}
        if action == "quarantine":
            record.action_quarantine_failed_batch()
            return {"redirect": "/odoo/action-base.action_open_view/%s" % record.id,
                    "record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model}
        return super().handle_action(record, action, params)


class WorkorderQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.wo"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Work Order"
    _kind_name = "wo"
    _target_model = "mrp.workorder"

    @api.model
    def handle_action(self, record, action, params):
        # Phase 3 — scan-to-act WO state transitions
        if action == "start":
            if hasattr(record, "button_start"):
                record.button_start()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": "WO started"}
        if action == "pause":
            if hasattr(record, "button_pending"):
                record.button_pending()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": "WO paused"}
        if action == "finish":
            if hasattr(record, "button_finish"):
                record.button_finish()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": "WO finished"}
        return super().handle_action(record, action, params)


class MoQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.mo"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Manufacturing Order"
    _kind_name = "mo"
    _target_model = "mrp.production"

    @api.model
    def handle_action(self, record, action, params):
        if action == "done":
            if hasattr(record, "button_mark_done"):
                record.button_mark_done()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": "MO marked done"}
        return super().handle_action(record, action, params)


class OpcuaQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.opcua"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — OPC-UA Endpoint"
    _kind_name = "opcua"
    _target_model = "southbrook.opcua.endpoint"

    @api.model
    def handle_action(self, record, action, params):
        if action == "poll":
            record.action_simulate_poll()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": "Simulate poll completed"}
        return super().handle_action(record, action, params)


class ShiftQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.shift"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Shift Handover"
    _kind_name = "shift"
    _target_model = "southbrook.shift.handover"

    @api.model
    def handle_action(self, record, action, params):
        if action == "ack":
            record.action_acknowledge()
            return {"record_name": record.display_name,
                    "record_id": record.id, "model": self._target_model,
                    "message": "Handover acknowledged"}
        return super().handle_action(record, action, params)


# ----------------------------------------------------------------------
# Defect-type QR — stateless kind. Scan a pre-printed defect QR to
# auto-create an NCR with that defect pre-selected. Phase 3 helper.
# ----------------------------------------------------------------------
class DefectQrKind(models.AbstractModel):
    _name = "southbrook.qr.kind.defect"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Pre-Defined Defect Type (stateless)"
    _kind_name = "defect"
    _target_model = "southbrook.mi.check"

    @api.model
    def get_record(self, ident):
        """For defect QRs, `ident` IS the defect_type selection key
        (e.g. 'scratch', 'edge_defect'). No record to fetch — return
        an empty recordset; handler creates one on action.

        The defect-type-as-ident pattern means a printed defect QR
        sheet works standalone: each cell on the sheet carries
        sb://defect/<defect_type>?... — scan it + the operator's
        cabinet/WO QR and an NCR drafts itself.
        """
        return self.env[self._target_model]

    @api.model
    def handle_action(self, record, action, params):
        """Creates a new NCR pre-filled. The defect_type comes from
        the *ident* (encoded in the QR itself). `params` may carry
        workorder_id for context attachment."""
        from odoo.http import request
        # Resolve defect_type from URL via request — the controller
        # passes it through after parsing. Fallback to params if a
        # caller invokes handle_action directly.
        defect_type = None
        if params and params.get("defect_type"):
            defect_type = params["defect_type"]
        # The controller sets request.qr_parsed_ident on dispatch
        # so downstream handlers see the defect_type carried in ident.
        elif request and hasattr(request, "qr_parsed_ident"):
            defect_type = request.qr_parsed_ident
        if not defect_type:
            raise UserError(_(
                "Defect-type QR is missing the defect_type encoded "
                "in the QR ident."))
        wo_id = (params or {}).get("workorder_id")
        vals = {
            "name": _("NCR from defect scan: %s") % defect_type,
            "x_sbk_defect_type": str(defect_type),
            "x_sbk_result": "fail",
        }
        if wo_id:
            try:
                vals["x_sbk_workorder_id"] = int(wo_id)
            except (TypeError, ValueError):
                pass
        new_ncr = self.env["southbrook.mi.check"].sudo().create(vals)
        return {
            "record_name": new_ncr.display_name,
            "record_id": new_ncr.id,
            "model": self._target_model,
            "message": _("NCR drafted for defect '%s'") % defect_type,
            "act_window": {
                "type": "ir.actions.act_window",
                "res_model": self._target_model,
                "res_id": new_ncr.id,
                "view_mode": "form",
                "target": "current",
            },
        }
