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

W069 (R3.14, 2026-06-27) — downtime → planner-notify cascade
============================================================

JTBD: "When a workcenter goes down (recorded in
southbrook.kitchen.workcenter.downtime), I want the planner notified
at downtime time, not at kanban-turn-red."

On downtime create (or state transition to 'active'), we find every
WO at the same workcenter currently in 'ready' or 'progress' whose
scheduled window overlaps the downtime window, then for each affected
WO we:

  1. Post a chatter message describing the conflict + suggested
     reschedule delta (downtime_min / workcenter capacity).
  2. Schedule a mail.activity on the WO targeting the planner
     (production_id.user_id, falling back to the downtime
     responsible_id), with deadline = today (planner action
     needed today).

We DO NOT auto-reschedule. The planner decides. The whole reason this
is a notify-only listener and not an auto-cascade is that any auto-
reschedule of a WO that's already in progress will surprise the
operator standing at the station. Plan-side moves are a human call.

The hook is idempotent per-WO per-downtime: we tag the chatter line
with the downtime id so re-firing the listener on a write that
re-touches state won't double-spam the WO with the same message.
"""
import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)


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
        # W069 — notify planner of any WOs that overlap this downtime.
        # Fire only when the downtime starts already 'active' (i.e. the
        # operator created it mid-event); draft creates trigger on the
        # subsequent action_start() write.
        for rec in records:
            if rec.state == "active":
                try:
                    rec._w069_notify_planner_of_affected_wos()
                except Exception:  # noqa: BLE001
                    _logger.exception(
                        "W069: downtime %s notify hook failed (non-fatal)",
                        rec.id,
                    )
        return records

    def write(self, vals):
        # Detect state transitions to 'active' so a draft → active
        # action_start() fires the same notify path the active-from-
        # create path uses. We compare BEFORE/AFTER state to avoid
        # re-firing on every unrelated write to an already-active row.
        going_active = vals.get("state") == "active"
        was_active = {rec.id: rec.state == "active" for rec in self}
        res = super().write(vals)
        if going_active:
            for rec in self:
                if not was_active.get(rec.id, False):
                    try:
                        rec._w069_notify_planner_of_affected_wos()
                    except Exception:  # noqa: BLE001
                        _logger.exception(
                            "W069: downtime %s notify hook failed "
                            "(non-fatal)", rec.id,
                        )
        return res

    # ------------------------------------------------------------------
    # W069 (R3.14, 2026-06-27) — planner notification listener
    # ------------------------------------------------------------------
    def _w069_notify_planner_of_affected_wos(self):
        """Find WOs at this downtime's WC currently in 'ready' or
        'progress' that overlap the downtime window, then post a
        chatter message + schedule a planner activity on each one.

        Notify-only. Never reschedules. Idempotent: each (downtime,
        WO) pair posts once — we tag the chatter line with the
        downtime id so a re-fire (a draft → active state flip after
        the create-time fire) does NOT double-spam.
        """
        self.ensure_one()
        if not self.workcenter_id:
            return self.env["mrp.workorder"].browse()

        # Overlap window. If the downtime has no end yet (it's just
        # started), use a 4-hour default lookahead so the planner
        # gets reasonable coverage of in-progress + immediately-next
        # WOs. The window expands automatically once date_end lands.
        dt_start = self.date_start or fields.Datetime.now()
        dt_end = self.date_end or (dt_start + timedelta(hours=4))

        Workorder = self.env["mrp.workorder"]
        # Overlap test: WO_start < downtime_end AND WO_end > downtime_start.
        # Native Odoo WO uses date_start (planned/actual start) and
        # date_finished (planned/actual finish).
        affected = Workorder.search([
            ("workcenter_id", "=", self.workcenter_id.id),
            ("state", "in", ("ready", "progress")),
            ("date_start", "!=", False),
            ("date_finished", "!=", False),
            ("date_start", "<", dt_end),
            ("date_finished", ">", dt_start),
        ])
        if not affected:
            return affected

        # Suggested reschedule delta — naive cap: the downtime duration
        # / 1 (single-channel WC) is just the downtime duration itself
        # (in hours). If the WC supports parallel jobs, the impact
        # divides by allows_parallel_jobs concurrency. The planner
        # decides; this is a hint only.
        wc = self.workcenter_id
        downtime_min = self.duration_min or (
            (dt_end - dt_start).total_seconds() / 60.0)
        parallel = 1
        if hasattr(wc, "allows_parallel_jobs") and wc.allows_parallel_jobs:
            # Best-effort: many "parallel" WCs still serialise around the
            # downtime cause (e.g. paint booth with multiple racks but
            # one cure cycle). Halve, do not zero, the delta.
            parallel = 2
        suggested_min = max(0.0, downtime_min / parallel)

        reason_label = dict(self._fields["reason"].selection).get(
            self.reason, self.reason or _("(no reason)"))

        # Resolve the planner: MO's responsible (production_id.user_id)
        # first, fall back to the downtime's logger.
        for wo in affected:
            # Dedupe per (downtime, WO). The chatter tag is a stable
            # marker we can grep for.
            tag = "[W069:dt=%d]" % self.id
            already = wo.message_ids.filtered(
                lambda m, t=tag: m.body and t in (m.body or ""))
            if already:
                continue

            planner = (
                (wo.production_id.user_id if wo.production_id else False)
                or self.responsible_id
                or self.env.user
            )
            severity = self._w069_severity_label(wo, dt_start, dt_end)
            body = _(
                "%(tag)s Work center <b>%(wc)s</b> went down at "
                "%(t)s (reason: %(r)s). This WO overlaps the outage "
                "and will likely slip by ~<b>%(delta).1f min</b>. "
                "Severity: <b>%(sev)s</b>. Planner action: review "
                "schedule (no auto-reschedule).",
                tag=tag,
                wc=wc.name or "?",
                t=dt_start,
                r=reason_label,
                delta=suggested_min,
                sev=severity,
            )
            wo.message_post(body=body, message_type="notification")

            # Schedule a mail.activity for the planner. Use the generic
            # 'todo' activity type — every Odoo install has it. Activity
            # deadline is TODAY because that is the JTBD ("notified at
            # downtime time, not at kanban-turn-red").
            #
            # R3 prod-bug fix (2026-06-30): mrp.workorder is NOT a
            # mail.activity.mixin target in v19 CE — calling
            # `wo.activity_schedule(...)` raised AttributeError on
            # every overlap, and the prior broad `except Exception`
            # swallowed it silently so NO planner was ever notified.
            # Schedule on the parent MO (mrp.production), which DOES
            # inherit mail.activity.mixin. Per scoping doc §6, this
            # path is fail-loud — we keep a narrow try/except so a
            # single bad WO doesn't abort the cron loop, but the
            # exception is logged at WARNING (not silently swallowed)
            # so future regressions surface in the log scrape.
            todo_type = self.env.ref(
                "mail.mail_activity_data_todo",
                raise_if_not_found=False,
            )
            if todo_type and planner and wo.production_id:
                try:
                    wo.production_id.activity_schedule(
                        act_type_xmlid="mail.mail_activity_data_todo",
                        summary=_("Reschedule review — WC %s downtime")
                                % (wc.name or "?"),
                        note=body,
                        user_id=planner.id,
                        date_deadline=fields.Date.context_today(self),
                    )
                except Exception as exc:  # noqa: BLE001
                    _logger.warning(
                        "W069: activity_schedule on MO %s (WO %s) "
                        "failed: %s -- planner %s NOT notified of "
                        "downtime overlap; investigate (was a silent "
                        "prod regression before R3 2026-06-30).",
                        wo.production_id.id, wo.id, exc,
                        planner.id,
                    )
        _logger.info(
            "W069: downtime %s notified planner of %d affected WO(s) "
            "at WC %s", self.id, len(affected), wc.name or "?",
        )
        return affected

    def _w069_severity_label(self, wo, dt_start, dt_end):
        """Severity proportional to overlap fraction of the WO window.
        >75% overlap = high, 25-75% = medium, <25% = low."""
        try:
            wo_start = wo.date_start
            wo_end = wo.date_finished
            if not (wo_start and wo_end and wo_end > wo_start):
                return _("medium")
            overlap_start = max(wo_start, dt_start)
            overlap_end = min(wo_end, dt_end)
            if overlap_end <= overlap_start:
                return _("low")
            overlap_sec = (overlap_end - overlap_start).total_seconds()
            wo_sec = (wo_end - wo_start).total_seconds()
            frac = overlap_sec / wo_sec if wo_sec > 0 else 0.0
            if frac >= 0.75:
                return _("high")
            if frac >= 0.25:
                return _("medium")
            return _("low")
        except Exception:  # noqa: BLE001
            return _("medium")

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
