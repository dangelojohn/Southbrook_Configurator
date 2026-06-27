# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.kitchen.workcenter.downtime — log of lost shop-floor time.

CE-safe model (brief §12) — no dependency on Enterprise-only
maintenance/quality modules. Stores why a work center was idle when
it was supposed to be producing. Drives the bottleneck / downtime-by-
reason / rework-impact reports in M4.

State machine:
  draft       inspector is still typing it up
  active      downtime is happening now (date_end is None)
  closed      downtime ended; date_end + duration_min are populated
  cancelled   inspector decided this isn't really downtime
"""
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


DOWNTIME_REASONS = [
    ("material_not_available", "Material Not Available"),
    ("drawing_issue", "Drawing / Spec Issue"),
    ("machine_breakdown", "Machine Breakdown"),
    ("tool_change", "Tool Change"),
    ("setup_time", "Setup Time"),
    ("color_finish_changeover", "Color / Finish Changeover"),
    ("waiting_previous_operation", "Waiting on Previous Operation"),
    ("waiting_quality_approval", "Waiting on Quality Approval"),
    ("rework", "Rework"),
    ("operator_unavailable", "Operator Unavailable"),
    ("subcontract_delay", "Subcontract Delay"),
    ("maintenance", "Planned Maintenance"),
    ("other", "Other"),
]


DOWNTIME_STATES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("closed", "Closed"),
    ("cancelled", "Cancelled"),
]


class SouthbrookKitchenWorkcenterDowntime(models.Model):
    _name = "southbrook.kitchen.workcenter.downtime"
    _description = "Southbrook Kitchen Work-Center Downtime"
    _order = "date_start desc, id desc"

    name = fields.Char(
        string="Description",
        required=True,
        default=lambda self: _("Downtime"),
    )
    state = fields.Selection(
        DOWNTIME_STATES,
        default="draft", required=True, tracking=True, index=True,
    )

    workcenter_id = fields.Many2one(
        comodel_name="mrp.workcenter",
        string="Work Center",
        required=True, index=True, ondelete="cascade",
    )
    workorder_id = fields.Many2one(
        comodel_name="mrp.workorder",
        string="Work Order",
        ondelete="set null", index=True,
        help="If the downtime is tied to a specific WO (e.g. the WO "
             "that was running when the machine went down).",
    )
    production_id = fields.Many2one(
        comodel_name="mrp.production",
        string="Manufacturing Order",
        related="workorder_id.production_id",
        store=True, readonly=True, index=True,
    )
    # W049 (R7.5, 2026-06-27) — shift attribution on downtime pivot.
    # Stored related so the pivot/graph can group-by "Shift" without
    # joining at query time. Empty when there's no attached WO or the
    # WO hasn't started — both treated as "Unassigned" in the report.
    x_sb_shift = fields.Selection(
        related="workorder_id.x_sb_shift",
        store=True, readonly=True, index=True,
        string="Shift",
    )

    date_start = fields.Datetime(
        string="Start",
        required=True, default=fields.Datetime.now, index=True,
    )
    date_end = fields.Datetime(
        string="End",
        index=True,
    )
    duration_min = fields.Float(
        string="Duration (min)",
        compute="_compute_duration",
        store=True, readonly=False,
        help="Computed from date_end − date_start when both are set. "
             "Editable so an operator who forgot to start the timer "
             "can backfill an estimate.",
    )

    reason = fields.Selection(
        DOWNTIME_REASONS,
        required=True, index=True,
    )
    notes = fields.Text()
    responsible_id = fields.Many2one(
        comodel_name="res.users",
        string="Logged By",
        default=lambda self: self.env.user,
    )

    # SAMI PRD MAINT-03 (2026-06-25) — auto-escalate operator downtime
    # into a maintenance.request so the maintenance crew sees it without
    # the operator having to switch apps.
    maintenance_request_id = fields.Many2one(
        comodel_name="maintenance.request",
        string="Maintenance Request",
        ondelete="set null",
        readonly=True,
        help="Auto-created when reason='machine_breakdown'. Operator "
             "can also click 'Escalate to Maintenance' for other "
             "reasons. Links so the original downtime row shows the "
             "maintenance request status.",
    )

    # Costing — populated lazily so the M3 downtime report can roll up
    # cost impact per workcenter / per reason. Reads workcenter.costs_
    # hour from the native mrp.workcenter field if present.
    downtime_cost = fields.Float(
        string="Downtime Cost",
        compute="_compute_downtime_cost",
        store=True,
        help="duration_min / 60 × workcenter_id.costs_hour. The cost "
             "of the lost time at the work center's hourly rate. M3 "
             "report aggregates this by reason and by station.",
    )

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for row in self:
            if row.date_start and row.date_end and row.date_end > row.date_start:
                delta = row.date_end - row.date_start
                row.duration_min = delta.total_seconds() / 60.0
            else:
                # Leave existing duration_min in place; the field is
                # editable so a manual estimate isn't blown away.
                if not row.duration_min:
                    row.duration_min = 0.0

    @api.depends("duration_min", "workcenter_id.costs_hour")
    def _compute_downtime_cost(self):
        for row in self:
            hourly = row.workcenter_id.costs_hour or 0.0
            row.downtime_cost = (row.duration_min / 60.0) * hourly

    @api.constrains("date_start", "date_end")
    def _check_date_order(self):
        for row in self:
            if row.date_end and row.date_start and row.date_end < row.date_start:
                raise ValidationError(_(
                    "Downtime end (%s) must be after start (%s)."
                ) % (row.date_end, row.date_start))

    @api.constrains("duration_min")
    def _check_non_negative_duration(self):
        for row in self:
            if row.duration_min < 0:
                raise ValidationError(_(
                    "Downtime duration cannot be negative (got %s)."
                ) % row.duration_min)

    # ------------------------------------------------------------------
    # State transitions — buttons surface on the form view.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Maintenance escalation (SAMI PRD MAINT-03, 2026-06-25)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Auto-escalate any breakdown to maintenance.request on create —
        # the operator doesn't have to click anything.
        for rec in records:
            if rec.reason == "machine_breakdown" and not rec.maintenance_request_id:
                try:
                    rec._spawn_maintenance_request(reason_label=_("Machine Breakdown"))
                except Exception:  # noqa: BLE001
                    # Never block a downtime log on maintenance auto-
                    # escalation. Operator can still hit the button.
                    pass
        return records

    def action_escalate_to_maintenance(self):
        """Operator-driven manual escalation for non-breakdown reasons.

        Idempotent — re-clicking on a record that already has a request
        just opens it instead of double-creating.
        """
        self.ensure_one()
        if self.maintenance_request_id:
            return self._action_open_maintenance_request()
        reason_label = dict(self._fields["reason"].selection).get(
            self.reason, self.reason)
        self._spawn_maintenance_request(reason_label=reason_label)
        return self._action_open_maintenance_request()

    def _spawn_maintenance_request(self, reason_label):
        self.ensure_one()
        Request = self.env["maintenance.request"]
        # mrp.workcenter has a related equipment_id via maintenance
        # module's link; if absent, fall back to no equipment (the
        # request still creates, just unassigned).
        equipment = self.workcenter_id.equipment_id if hasattr(
            self.workcenter_id, "equipment_id") else False
        req = Request.create({
            "name": _("Downtime escalation: %(r)s @ %(wc)s",
                      r=reason_label, wc=self.workcenter_id.name or "?"),
            "description": _(
                "Auto-created from downtime log %(dt)s.\n"
                "Workcenter: %(wc)s\n"
                "Reason: %(r)s\n"
                "Started: %(t)s\n"
                "Notes: %(n)s",
                dt=self.name or self.id,
                wc=self.workcenter_id.display_name or "?",
                r=reason_label,
                t=self.date_start,
                n=self.notes or "(none)",
            ),
            "maintenance_type": "corrective",
            "equipment_id": equipment.id if equipment else False,
            "user_id": self.workcenter_id.equipment_id.technician_user_id.id
                if equipment and equipment.technician_user_id else False,
        })
        self.maintenance_request_id = req.id
        # Emit ops.event so the Kitchen Ops dashboard activity feed
        # picks it up — non-fatal if event model absent.
        try:
            self.env["southbrook.ops.event"].emit(
                "install_risk",
                _("Maintenance request %(r)s spawned from downtime at %(wc)s",
                  r=req.name or "?", wc=self.workcenter_id.name or "?"),
                res_model="maintenance.request",
                res_id=req.id,
                severity="alert",
            )
        except Exception:  # noqa: BLE001
            pass
        return req

    def _action_open_maintenance_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Maintenance Request"),
            "res_model": "maintenance.request",
            "res_id": self.maintenance_request_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_start(self):
        for row in self:
            if row.state in ("draft",):
                row.write({"state": "active", "date_start": fields.Datetime.now()})

    def action_close(self):
        for row in self:
            row.write({"state": "closed", "date_end": fields.Datetime.now()})

    def action_cancel(self):
        for row in self:
            row.state = "cancelled"
