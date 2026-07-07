# SPDX-License-Identifier: LGPL-3.0-only
"""Workcenter capacity row — planned vs available hours per week."""
import logging
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookMesMpsWorkcenterCapacity(models.Model):
    _name = "southbrook.mes_mps.workcenter_capacity"
    _description = "Workcenter Weekly Capacity"
    _order = "week_start desc, workcenter_id"

    _unique_wc_week = models.Constraint(
        "UNIQUE(workcenter_id, week_start)",
        "A capacity row for this workcenter and week already exists.",
    )

    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        required=True,
        ondelete="cascade",
    )
    week_start = fields.Date(string="Week Start (Mon)", required=True)
    available_hours = fields.Float(
        string="Available Hours",
        required=True,
        default=40.0,
        help="Pulled from the workcenter's resource.calendar when "
        "action_compute_load() runs.",
    )
    planned_hours = fields.Float(
        string="Planned Hours",
        compute="_compute_planned_hours",
        store=True,
    )
    load_pct = fields.Float(
        string="Load %",
        compute="_compute_load",
        store=True,
        help="planned / available × 100",
    )
    is_overloaded = fields.Boolean(
        string="Overloaded",
        compute="_compute_load",
        store=True,
    )

    @api.depends("workcenter_id", "week_start")
    def _compute_planned_hours(self):
        """Sum scheduled durations of MO operations landing in week.

        Native CE has ``mrp.workorder`` (the model exists in CE; only
        the *editor* lives in Enterprise's ``mrp_workorder``).  If a
        workcenter has no operations, fall back to summing the
        producing MO durations weighted by the routing share — but in
        most kitchen MO setups the workorder row is present and that
        gives us a clean number.
        """
        WO = self.env["mrp.workorder"]
        for rec in self:
            if not (rec.workcenter_id and rec.week_start):
                rec.planned_hours = 0.0
                continue
            week_end = rec.week_start + timedelta(days=7)
            domain = [
                ("workcenter_id", "=", rec.workcenter_id.id),
                ("date_start", ">=", rec.week_start),
                ("date_start", "<", week_end),
                # Real Odoo 19 CE WO states (blocked/ready/progress);
                # 'pending'/'waiting' never existed and dropped all
                # blocked (dependency-waiting) load from the week's total.
                ("state", "in", ("blocked", "ready", "progress")),
            ]
            wos = WO.search(domain)
            # duration_expected is minutes on mrp.workorder.
            total_min = sum(wos.mapped("duration_expected") or [])
            rec.planned_hours = total_min / 60.0

    @api.depends("planned_hours", "available_hours")
    def _compute_load(self):
        for rec in self:
            if rec.available_hours:
                rec.load_pct = (rec.planned_hours / rec.available_hours) * 100.0
            else:
                rec.load_pct = 0.0
            rec.is_overloaded = rec.load_pct > 100.0

    def action_compute_load(self):
        """Refresh available_hours from resource.calendar + recompute."""
        for rec in self:
            wc = rec.workcenter_id
            if not (wc and rec.week_start):
                continue
            avail = 40.0
            calendar = wc.resource_calendar_id
            if calendar:
                start_dt = datetime.combine(rec.week_start, time(0, 0))
                end_dt = start_dt + timedelta(days=7)
                try:
                    intervals = calendar._work_intervals_batch(
                        start_dt, end_dt
                    )
                    # _work_intervals_batch returns a dict keyed by
                    # resource id; key 0 is the "calendar without
                    # resource" bucket which is what we want.
                    if intervals:
                        bucket = intervals.get(False) or next(
                            iter(intervals.values())
                        )
                        total = timedelta()
                        for start, stop, _meta in bucket:
                            total += stop - start
                        avail = total.total_seconds() / 3600.0
                except Exception as exc:  # pragma: no cover
                    _logger.warning(
                        "Capacity calendar lookup failed for %s: %s",
                        wc.display_name,
                        exc,
                    )
            rec.available_hours = avail
        # Forced recompute via cache invalidate — the @api.depends
        # already covers writes above, but invalidate covers manual
        # menu calls.
        self.invalidate_recordset(["planned_hours", "load_pct"])
        return True
