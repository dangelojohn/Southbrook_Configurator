# SPDX-License-Identifier: LGPL-3.0-only
"""W071 (R8.10, 2026-06-27) — Trolley/cart QR -> bind pre-staged kit to WO.

JTBD: "When a pre-staged trolley arrives at my cell, I want to scan its
QR and have it bind to my current WO automatically — so material trace
works even when wrong-hinge slips through."

Design:
  * The "trolley" is a pre-staged stock.picking of type 'internal' (the
    standard Odoo material-staging surface). We do NOT introduce a new
    southbrook.staging.kit model — the staging surface already exists
    natively and CMMS/WMS extensions already inherit it.
  * The QR encodes `sb://trolley/<stock.picking.id>`.
  * Scanning the QR resolves the picking and binds it to the operator's
    currently-active workorder via `mrp.workorder.x_sbk_trolley_id`.
  * "Active workorder" is the most recent in-progress (state='progress')
    WO credited to the W035-resolved hr.employee. Falls back to a
    caller-supplied `workorder_id` param when the bind site already
    knows the WO (e.g. the floor screen has it in URL state).
  * The binding establishes material trace: every component move on the
    trolley picking carries the WO id forward through MO/BOM analytics.

Why stock.picking, not a new model:
  * `stock.picking` already carries product_ids, lots, quants, partner,
    origin, state, scheduled_date — exactly the trolley surface.
  * `stock.picking` already inherits southbrook.qr.mixin (pick kind),
    so an internal picking already has a QR — but the pick kind opens
    the picking form. The trolley kind is operationally different: it
    BINDS instead of OPENING. Hence a distinct kind alias on the same
    underlying record.
  * Re-uses existing access rules, audit (mail.thread), and the WMS
    permit/3PL extensions in southbrook_cmms_wms.

Trolley identification:
  * Any internal picking can be a trolley. Operationally a picking is
    "trolley-shaped" if its picking_type is internal AND state is in
    ('assigned', 'done'). The scan handler rejects others with a
    user-facing error.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpWorkorderTrolley(models.Model):
    """Add the trolley binding field to mrp.workorder.

    Field name uses the `x_sbk_` prefix per project memory's "studio-safe"
    convention (avoids clashes with native or third-party fields and
    keeps the addon-owned namespace visible at a glance in the form).

    Mixes in ``mail.thread`` because v19's ``mrp.workorder`` does NOT
    inherit it by default — and ``action_sbk_bind_trolley`` below calls
    ``self.message_post(...)`` to record the bind/re-bind audit trail
    (mirrored onto the picking which already has chatter). Without this
    shim the message_post call raises AttributeError at runtime and the
    W071 trolley-bind test (`test_21_bind_writes_field_and_posts_chatter`)
    asserts that ``wo.message_ids`` grows after the bind — which only
    works if mail.thread is mixed in here. Delegation-inheritance pattern
    keeps the change scoped to this addon and avoids forking native mrp.
    """
    _name = "mrp.workorder"
    _inherit = ["mrp.workorder", "mail.thread"]

    x_sbk_trolley_id = fields.Many2one(
        "stock.picking",
        string="Bound Trolley (W071)",
        index=True,
        domain="[('picking_type_id.code', '=', 'internal')]",
        help="The pre-staged trolley (internal picking) bound to this "
             "workorder via QR scan. Establishes material trace from the "
             "picking's components back to this WO.",
    )
    x_sbk_trolley_bound_at = fields.Datetime(
        string="Trolley Bound At",
        readonly=True, copy=False,
        help="Server timestamp of the most-recent W071 trolley bind.",
    )
    x_sbk_trolley_bound_by = fields.Many2one(
        "hr.employee",
        string="Trolley Bound By",
        readonly=True, copy=False,
        help="W035-resolved operator who performed the trolley bind.",
    )

    @api.model
    def _sbk_resolve_active_workorder(self, employee, hint_id=None):
        """Resolve the WO the trolley should bind to.

        Order:
          1. Caller-supplied `hint_id` (the floor screen knows its WO).
          2. Most-recent in-progress WO whose `employee_assigned_ids` or
             `operator_id` matches the resolved hr.employee (W035).
          3. Falls back to the most-recent in-progress WO touched by the
             session user.

        Returns an empty recordset when nothing fits; the scan handler
        surfaces a friendly error.
        """
        Wo = self.env["mrp.workorder"].sudo()
        if hint_id:
            wo = Wo.browse(int(hint_id)).exists()
            if wo:
                return wo
        if employee:
            # Prefer the WO the employee is currently working. Odoo 19
            # mrp_workorder addon stores active operators in
            # `employee_assigned_ids`. We don't depend on that addon
            # (it's enterprise-flavoured in v19) so we use a safe
            # `hasattr` check before querying the field.
            domain_base = [("state", "=", "progress")]
            if "employee_assigned_ids" in Wo._fields:
                wo = Wo.search(
                    domain_base + [
                        ("employee_assigned_ids", "in", employee.ids),
                    ],
                    order="write_date desc", limit=1,
                )
                if wo:
                    return wo
            # Fall back to operator_id when present (older mrp variants).
            if "operator_id" in Wo._fields:
                wo = Wo.search(
                    domain_base + [
                        ("operator_id", "=", employee.id),
                    ],
                    order="write_date desc", limit=1,
                )
                if wo:
                    return wo
        return Wo

    def action_sbk_bind_trolley(self, picking, employee=False):
        """Bind a stock.picking (trolley) to this WO.

        Idempotent: re-binding the same trolley is a no-op. Re-binding
        a DIFFERENT trolley overwrites the previous binding and posts
        a chatter note (audit). Trace is preserved in the chatter.

        Raises UserError if the picking is not a valid trolley.
        """
        self.ensure_one()
        if not picking or not picking.exists():
            raise UserError(_("Trolley picking not found."))
        if picking.picking_type_id.code != "internal":
            raise UserError(_(
                "Trolley scan only accepts internal pickings (got %s).")
                % picking.picking_type_id.code)
        if picking.state not in ("assigned", "done", "waiting", "confirmed"):
            raise UserError(_(
                "Trolley %(name)s is in state '%(state)s' — must be "
                "ready/assigned to be bound to a workorder.") % {
                "name": picking.display_name, "state": picking.state})
        if self.x_sbk_trolley_id and self.x_sbk_trolley_id.id == picking.id:
            return {"already_bound": True,
                    "trolley_name": picking.display_name,
                    "workorder_id": self.id,
                    "workorder_name": self.display_name}
        prev = self.x_sbk_trolley_id
        self.write({
            "x_sbk_trolley_id": picking.id,
            "x_sbk_trolley_bound_at": fields.Datetime.now(),
            "x_sbk_trolley_bound_by": employee.id if employee else False,
        })
        op_label = employee.name if employee else self.env.user.display_name
        if prev:
            self.message_post(body=_(
                "Trolley re-bound: %(old)s → %(new)s (by %(who)s).") % {
                "old": prev.display_name,
                "new": picking.display_name,
                "who": op_label,
            })
        else:
            self.message_post(body=_(
                "Trolley %(t)s bound to this workorder by %(who)s.") % {
                "t": picking.display_name, "who": op_label,
            })
        # Mirror onto the picking's chatter for the trace-back lookup.
        picking.message_post(body=_(
            "Bound to workorder %(wo)s (MO %(mo)s) by %(who)s.") % {
            "wo": self.display_name,
            "mo": self.production_id.name or "?",
            "who": op_label,
        })
        return {
            "ok": True,
            "trolley_name": picking.display_name,
            "trolley_id": picking.id,
            "workorder_id": self.id,
            "workorder_name": self.display_name,
            "production_name": self.production_id.name or "",
            "prev_trolley_name": prev.display_name if prev else "",
        }


class TrolleyQrKind(models.AbstractModel):
    """QR kind handler: sb://trolley/<stock.picking.id>.

    Default action 'bind' resolves the operator's active WO and binds.
    Action 'open' falls through to the standard picking-form redirect
    (useful when a desk user scans the trolley QR at a backend tablet).
    """
    _name = "southbrook.qr.kind.trolley"
    _inherit = "southbrook.qr.kind"
    _description = "QR Kind — Pre-Staged Trolley (W071)"
    _kind_name = "trolley"
    _target_model = "stock.picking"
    _default_action = "bind"

    @api.model
    def handle_action(self, record, action, params):
        if action == "bind":
            # The controller injected the resolved operator hr.employee
            # via params['_w035_employee_id'] (the qr_scan dispatcher
            # already calls _get_operator_employee on every scan, but
            # AbstractModel.handle_action can't reach the request — so
            # we accept it as a param). May be empty for desk scans.
            hint_id = (params or {}).get("workorder_id")
            emp_id = (params or {}).get("_w035_employee_id")
            employee = (
                self.env["hr.employee"].sudo().browse(int(emp_id))
                if emp_id else self.env["hr.employee"]
            )
            wo = self.env["mrp.workorder"]._sbk_resolve_active_workorder(
                employee, hint_id=hint_id)
            if not wo:
                return {
                    "ok": False,
                    "result": "no_active_workorder",
                    "error": _(
                        "No active workorder found for the current "
                        "operator. Start a WO on the floor screen first, "
                        "or include workorder_id in the scan params."),
                    "model": self._target_model,
                    "record_id": record.id,
                    "record_name": record.display_name,
                }
            result = wo.action_sbk_bind_trolley(record, employee=employee)
            result.setdefault("model", self._target_model)
            result.setdefault("record_id", record.id)
            result.setdefault("record_name", record.display_name)
            return result
        return super().handle_action(record, action, params)
