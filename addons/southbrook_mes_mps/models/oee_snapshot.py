# SPDX-License-Identifier: LGPL-3.0-only
"""OEE snapshot — per-shift availability × performance × quality."""
import logging
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookMesMpsOeeSnapshot(models.Model):
    _name = "southbrook.mes_mps.oee_snapshot"
    _description = "OEE Snapshot (per Workcenter / Shift)"
    _order = "shift_date desc, workcenter_id, shift"

    _unique_wc_shift = models.Constraint(
        "UNIQUE(workcenter_id, shift_date, shift)",
        "An OEE snapshot for this workcenter/date/shift already exists.",
    )

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        required=True,
        ondelete="cascade",
    )
    shift_date = fields.Date(string="Shift Date", required=True)
    shift = fields.Selection(
        [
            ("morning", "Morning"),
            ("afternoon", "Afternoon"),
            ("night", "Night"),
        ],
        required=True,
        default="morning",
    )
    planned_minutes = fields.Float(string="Planned Minutes", required=True)
    actual_run_minutes = fields.Float(string="Run Minutes", required=True)
    actual_idle_minutes = fields.Float(string="Idle Minutes", required=True)
    actual_downtime_minutes = fields.Float(
        string="Downtime Minutes", required=True
    )
    units_produced = fields.Integer(string="Units Produced", required=True)
    units_target = fields.Integer(string="Units Target", required=True)
    units_rejected = fields.Integer(string="Units Rejected", required=True)

    availability = fields.Float(
        string="Availability",
        compute="_compute_oee",
        store=True,
        digits=(3, 4),
    )
    performance = fields.Float(
        string="Performance",
        compute="_compute_oee",
        store=True,
        digits=(3, 4),
    )
    quality = fields.Float(
        string="Quality",
        compute="_compute_oee",
        store=True,
        digits=(3, 4),
    )
    oee = fields.Float(
        string="OEE",
        compute="_compute_oee",
        store=True,
        digits=(3, 4),
    )
    oee_class = fields.Selection(
        [
            ("world_class", "World Class (>85%)"),
            ("good", "Good (>60%)"),
            ("typical", "Typical (>40%)"),
            ("unacceptable", "Unacceptable"),
        ],
        compute="_compute_oee",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                seq = self.env["ir.sequence"].next_by_code(
                    "southbrook.mes_mps.oee_snapshot"
                )
                vals["name"] = seq or (
                    "OEE_SNAP/%s" % (vals.get("shift_date") or "NEW")
                )
        return super().create(vals_list)

    @api.depends(
        "planned_minutes",
        "actual_run_minutes",
        "actual_idle_minutes",
        "actual_downtime_minutes",
        "units_produced",
        "units_target",
        "units_rejected",
    )
    def _compute_oee(self):
        for rec in self:
            # Availability = (planned − downtime) / planned, clamped.
            if rec.planned_minutes:
                avail = (
                    rec.planned_minutes - rec.actual_downtime_minutes
                ) / rec.planned_minutes
            else:
                avail = 0.0
            avail = max(0.0, min(1.0, avail))

            # Performance = (units × ideal_cycle_time) / actual_run.
            # We approximate ideal_cycle_time as the target rate
            # implied by units_target spread across planned_minutes
            # (the calling cron uses workcenter capacity/100). Falls
            # back to 0 when inputs are missing.
            if rec.actual_run_minutes and rec.units_target:
                ideal_cycle = rec.planned_minutes / rec.units_target
                perf = (rec.units_produced * ideal_cycle) / rec.actual_run_minutes
            else:
                perf = 0.0
            perf = max(0.0, min(1.0, perf))

            # Quality = (produced − rejected) / produced.
            if rec.units_produced:
                qual = (
                    rec.units_produced - rec.units_rejected
                ) / rec.units_produced
            else:
                qual = 0.0
            qual = max(0.0, min(1.0, qual))

            rec.availability = avail
            rec.performance = perf
            rec.quality = qual
            rec.oee = avail * perf * qual

            if rec.oee > 0.85:
                rec.oee_class = "world_class"
            elif rec.oee > 0.6:
                rec.oee_class = "good"
            elif rec.oee > 0.4:
                rec.oee_class = "typical"
            else:
                rec.oee_class = "unacceptable"

    @api.model
    def action_compute_from_workcenter_productivity(self, snap_date=None):
        """Roll productivity rows up into one OEE snapshot per WC/shift.

        Reads ``mrp.workcenter.productivity`` (the CE downtime/loss
        log) for ``snap_date`` and aggregates by loss_id.loss_type.
        """
        Productivity = self.env["mrp.workcenter.productivity"]
        Workcenter = self.env["mrp.workcenter"]
        if not snap_date:
            snap_date = fields.Date.context_today(self)
        if isinstance(snap_date, str):
            snap_date = fields.Date.from_string(snap_date)
        day_start = datetime.combine(snap_date, time(0, 0))
        day_end = day_start + timedelta(days=1)

        domain = [
            ("date_start", ">=", day_start),
            ("date_start", "<", day_end),
        ]
        rows = Productivity.search(domain)
        if not rows:
            _logger.info(
                "OEE roll-up: no productivity rows for %s", snap_date
            )
            return self.browse()

        snapshots = self.browse()
        per_wc = {}
        for row in rows:
            per_wc.setdefault(row.workcenter_id.id, []).append(row)

        for wc_id, wc_rows in per_wc.items():
            wc = Workcenter.browse(wc_id)
            run_min = 0.0
            idle_min = 0.0
            down_min = 0.0
            for r in wc_rows:
                # duration is minutes on mrp.workcenter.productivity.
                loss_type = (
                    r.loss_id.loss_type if r.loss_id else "productive"
                )
                if loss_type == "productive":
                    run_min += r.duration
                elif loss_type == "performance":
                    idle_min += r.duration
                else:  # availability + quality both block availability
                    down_min += r.duration
            planned = max(run_min + idle_min + down_min, 8 * 60.0)
            # Derive units from the workorders the day's productivity rows
            # reference. Hardcoding units to 0 forced Performance and Quality
            # to 0 in _compute_oee, so EVERY cron snapshot reported OEE 0% /
            # "unacceptable" and dragged the 7-day average toward 0 — the
            # headline metric was dead. qty_produced / qty_production give the
            # real produced/target counts (rejected isn't tracked per-WO here,
            # so Quality reads 1.0 when production data exists).
            workorders = self.env["mrp.workorder"].browse()
            for r in wc_rows:
                if r.workorder_id:
                    workorders |= r.workorder_id
            units_produced = int(round(sum(workorders.mapped("qty_produced"))))
            units_target = int(round(sum(workorders.mapped("qty_production"))))
            vals = {
                "workcenter_id": wc.id,
                "shift_date": snap_date,
                "shift": "morning",
                "planned_minutes": planned,
                "actual_run_minutes": run_min,
                "actual_idle_minutes": idle_min,
                "actual_downtime_minutes": down_min,
                "units_produced": units_produced,
                "units_target": units_target,
                "units_rejected": 0,
            }
            existing = self.search(
                [
                    ("workcenter_id", "=", wc.id),
                    ("shift_date", "=", snap_date),
                    ("shift", "=", "morning"),
                ],
                limit=1,
            )
            if existing:
                existing.write(vals)
                snapshots |= existing
            else:
                snapshots |= self.create(vals)
        return snapshots
