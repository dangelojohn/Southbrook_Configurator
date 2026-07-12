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
from odoo.exceptions import AccessError, UserError


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
    def get_record(self, ident):
        """W055 / R1.12 — resolve by MO name (WH/MO/00023) OR int id.

        The cabinet label QR now encodes the MO's *name* rather than
        its raw id. The name is preserved across ECO-driven MO rebuilds
        (the new MO inherits the same name with a -1 suffix at worst);
        the bare id is not. This override:

        1. tries int parse first (legacy callers still work);
        2. on miss, searches mrp.production by name;
        3. on a name with an ECO-rebuild suffix (e.g. WH/MO/00023-1),
           returns the latest matching MO so a printed label always
           opens the *current* MO for that cabinet.

        Backward compat — already-printed labels with raw int ids hit
        path #1 and resolve exactly as before.
        """
        # Path 1 — int parse (legacy + non-name idents)
        try:
            rid = int(ident)
            rec = self.env["mrp.production"].browse(rid).exists()
            if rec:
                rec.check_access_rights("read")
                rec.check_access_rule("read")
                return rec
        except (TypeError, ValueError):
            pass
        # Path 2 — name lookup
        if isinstance(ident, str):
            Mo = self.env["mrp.production"].sudo()
            # Exact match first.
            rec = Mo.search([("name", "=", ident)], limit=1)
            if not rec:
                # Path 3 — ECO-rebuild fan-out (name + numeric suffix).
                # E.g. printed label says WH/MO/00023; ECO rebuilt to
                # WH/MO/00023-1 → resolve to the most recent one.
                rec = Mo.search(
                    [("name", "=ilike", f"{ident}%")],
                    order="id desc", limit=1,
                )
            if rec:
                # Re-bind via env(user=self.env.user) so ACL holds.
                rec = self.env["mrp.production"].browse(rec.id)
                rec.check_access_rights("read")
                rec.check_access_rule("read")
                return rec
        # Fall through to default int-only error path
        return super().get_record(ident)

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

    # SAMI PRD (2026-06-26) — how long after a wo/mo/asbuilt/pkg scan
    # does the next defect scan still inherit that record as context?
    # W018 (2026-06-27, R5.3): widened from 300s -> 900s. The 5-min
    # default was too tight for the realistic floor walk: operator
    # scans WO at the station, walks to the defect-QR sheet at the
    # quality station 30-90s away, hunts down the right cell, scans
    # it. Doubling-plus to 15 min covers operators who scan-then-
    # walk-to-station without losing context.
    # Tunable per-site via ir.config_parameter
    # `southbrook.qr_kit.defect_context_window_seconds`.
    _DEFAULT_DEFECT_CONTEXT_SEC = 900

    @api.model
    def _resolve_workorder_from_context(self):
        """Find the WO most recently scanned by the current user
        in the configurable context window. Walks wo/mo/asbuilt/pkg
        kinds to find a WO id. Returns int WO id or False."""
        from datetime import datetime, timedelta
        Param = self.env["ir.config_parameter"].sudo()
        try:
            window = int(Param.get_param(
                "southbrook.qr_kit.defect_context_window_seconds",
                self._DEFAULT_DEFECT_CONTEXT_SEC))
        except (TypeError, ValueError):
            window = self._DEFAULT_DEFECT_CONTEXT_SEC
        cutoff = datetime.now() - timedelta(seconds=window)
        Log = self.env["southbrook.qr.scan.log"].sudo()
        recent = Log.search([
            ("user_id", "=", self.env.user.id),
            ("result", "=", "ok"),
            ("target_model", "in",
             ["mrp.workorder", "mrp.production",
              "southbrook.asbuilt", "sb.production.package"]),
            ("create_date", ">=", cutoff),
        ], limit=1, order="create_date desc")
        if not recent or not recent.target_id:
            return False
        if recent.target_model == "mrp.workorder":
            return recent.target_id
        if recent.target_model == "mrp.production":
            mo = self.env["mrp.production"].sudo().browse(
                recent.target_id).exists()
            return mo.workorder_ids[:1].id if mo and mo.workorder_ids else False
        if recent.target_model == "southbrook.asbuilt":
            ab = self.env["southbrook.asbuilt"].sudo().browse(
                recent.target_id).exists()
            if ab and ab.production_id and ab.production_id.workorder_ids:
                return ab.production_id.workorder_ids[:1].id
            return False
        if recent.target_model == "sb.production.package":
            pkg = self.env["sb.production.package"].sudo().browse(
                recent.target_id).exists()
            if pkg and pkg.mo_id and pkg.mo_id.workorder_ids:
                return pkg.mo_id.workorder_ids[:1].id
            return False
        return False

    @api.model
    def handle_action(self, record, action, params):
        """Creates a new NCR pre-filled. The defect_type comes from
        the *ident* (encoded in the QR itself). `params` may carry
        workorder_id for context attachment.

        Phase 8 (2026-06-26): if workorder_id not passed in params,
        the handler walks the user's recent scan log to auto-resolve
        the WO from a preceding wo/mo/asbuilt/pkg scan within the
        configurable context window."""
        from odoo.http import request
        # Resolve defect_type from URL via request — the controller
        # passes it through after parsing. Fallback to params if a
        # caller invokes handle_action directly.
        defect_type = None
        if params and params.get("defect_type"):
            defect_type = params["defect_type"]
        # The controller sets request.qr_parsed_ident on dispatch
        # so downstream handlers see the defect_type carried in ident.
        # `request` is a LocalProxy — accessing it (even `bool(request)`)
        # raises RuntimeError("object is not bound") when there is no HTTP
        # context (handler called directly / from tests / internally), so
        # guard the access rather than let it crash.
        else:
            try:
                defect_type = getattr(request, "qr_parsed_ident", None)
            except RuntimeError:
                defect_type = None
        if not defect_type:
            raise UserError(_(
                "Defect-type QR is missing the defect_type encoded "
                "in the QR ident."))
        # M2: recording a defect is a STAFF action. The `defect` kind is
        # stateless (get_record returns an empty recordset → NO check_access
        # runs), and the create below is sudo'd — so without this a portal
        # (share=True) user holding a signed, never-expiring defect payload
        # (embedded on the auth=user defect-sheet) could mint superuser NCRs.
        if self.env.user.share:
            raise AccessError(_("Only staff may record a defect."))
        # Caller-supplied workorder_id wins; else look at scan context.
        wo_id = (params or {}).get("workorder_id")
        context_resolved = False
        if not wo_id:
            wo_id = self._resolve_workorder_from_context()
            context_resolved = bool(wo_id)
        vals = {
            "name": _("NCR from defect scan: %s") % defect_type,
            "x_sbk_defect_type": str(defect_type),
            "x_sbk_result": "fail",
        }
        if wo_id:
            try:
                wo_id_int = int(wo_id)
            except (TypeError, ValueError):
                wo_id_int = None
            # IDOR guard: only attribute the NCR to a work order the caller may
            # actually access. `params["workorder_id"]` was previously trusted
            # as-is, letting a caller pin a fabricated 'fail' NCR onto ANY WO id.
            if wo_id_int:
                wo = self.env["mrp.workorder"].browse(wo_id_int).exists()
                if wo:
                    try:
                        wo.check_access("read")
                        vals["x_sbk_workorder_id"] = wo_id_int
                    except AccessError:
                        if not context_resolved:
                            raise
        new_ncr = self.env["southbrook.mi.check"].sudo().create(vals)
        # If we auto-filled WO from context, post a chatter note so the
        # inspector knows which scan was used.
        if context_resolved:
            try:
                new_ncr.message_post(body=_(
                    "Auto-linked to WO from your previous scan within "
                    "the defect-context window (15 min default)."))
            except Exception:  # noqa: BLE001
                pass
        # W018 (R5.3) — echo the resolved WO in the toast so the
        # operator can confirm at a glance that the NCR linked to the
        # right work order. "Drafted defect" alone left them guessing.
        # Shape: "Drafted defect 'scratch' -> WO00123 (Edgebanding)"
        resolved_wo = False
        if wo_id:
            try:
                resolved_wo = self.env["mrp.workorder"].sudo().browse(
                    int(wo_id)).exists()
            except (TypeError, ValueError):
                resolved_wo = False
        if resolved_wo:
            wo_label = resolved_wo.display_name or (
                "WO%05d" % resolved_wo.id)
            op_label = ""
            if resolved_wo.workcenter_id:
                op_label = " (%s)" % resolved_wo.workcenter_id.name
            elif resolved_wo.operation_id:
                op_label = " (%s)" % resolved_wo.operation_id.name
            message = _(
                "Drafted defect '%(defect)s' -> %(wo)s%(op)s"
            ) % {"defect": defect_type, "wo": wo_label, "op": op_label}
        else:
            message = _("NCR drafted for defect '%s' "
                        "(no recent WO scan -- link manually)") % defect_type
        return {
            "record_name": new_ncr.display_name,
            "record_id": new_ncr.id,
            "model": self._target_model,
            "message": message,
            "wo_id": resolved_wo.id if resolved_wo else False,
            "wo_name": (resolved_wo.display_name if resolved_wo else ""),
            "workcenter_name": (
                resolved_wo.workcenter_id.name
                if resolved_wo and resolved_wo.workcenter_id else ""),
            "context_resolved": context_resolved,
            "act_window": {
                "type": "ir.actions.act_window",
                "res_model": self._target_model,
                "res_id": new_ncr.id,
                "view_mode": "form",
                "target": "current",
            },
        }
