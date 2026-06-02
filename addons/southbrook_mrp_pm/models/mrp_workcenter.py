# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.workcenter extension — PM KPI computed fields.

M10 (Manufacturing PM JTBD 2026-06-01): the JTBD analysis called
out 'no consolidated PM dashboard'. The Odoo standard mrp module
has computed counts (workorder_ready_count etc.) but they're
generic shop-floor counters, not framed for the PM's daily walk.

This commit adds 4 computed scalars per work center that the M10
kanban dashboard renders as a tile per station. All four refresh
live (no stored cache) — the PM hits the dashboard and sees the
current state without a manual refresh.

  southbrook_pm_inflight_count    work orders at this station in
                                   pending/ready/progress/waiting

  southbrook_pm_throughput_today   work orders at this station
                                   that finished today (state=done
                                   AND date_finished >= today 00:00)

  southbrook_pm_late_count         MOs with at least one work order
                                   at this station whose date_deadline
                                   has passed and which aren't done

  southbrook_pm_equipment_alerts   maintenance.equipment records at
                                   this station whose
                                   southbrook_condition is NOT 'good'
                                   (fair / watch / critical / offline)

Each is a depends-light computed field — the PM rebuild trigger is
hitting the dashboard, not Odoo's compute invalidation. The
@api.depends keys are intentionally loose because we don't want
mrp.workorder.write() events to trigger workcenter recomputes
across the whole shop on every barcode scan.
"""
from datetime import datetime, time

from odoo import _, api, fields, models


# Same gate states the floor portal uses. Keeping the constant local
# here avoids cross-module imports for what's effectively a literal.
_IN_FLIGHT_WO_STATES = ("pending", "waiting", "ready", "progress")


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    southbrook_pm_inflight_count = fields.Integer(
        string="In-Flight WOs",
        compute="_compute_southbrook_pm_kpis",
        help=(
            "Work orders queued at this station — pending / waiting / "
            "ready / progress. The 'how busy is this station right "
            "now' metric."
        ),
    )

    southbrook_pm_throughput_today = fields.Integer(
        string="Done Today",
        compute="_compute_southbrook_pm_kpis",
        help=(
            "Work orders completed at this station since midnight. "
            "Coarse-grain throughput — fine-grain OEE comes once "
            "the timer-row infrastructure is in place."
        ),
    )

    southbrook_pm_late_count = fields.Integer(
        string="Late MOs",
        compute="_compute_southbrook_pm_kpis",
        help=(
            "Manufacturing orders with at least one work order at "
            "this station whose date_deadline has passed and which "
            "are not yet done."
        ),
    )

    southbrook_pm_equipment_alerts = fields.Integer(
        string="Equipment Alerts",
        compute="_compute_southbrook_pm_kpis",
        help=(
            "Equipment at this station whose condition is anything "
            "other than 'good' — fair / watch / critical / offline. "
            "Tap the workcenter to see which machines."
        ),
    )

    @api.depends_context("uid")
    def _compute_southbrook_pm_kpis(self):
        Wo = self.env["mrp.workorder"].sudo()
        Mo = self.env["mrp.production"].sudo()
        Eq = self.env["maintenance.equipment"].sudo()

        today_start = fields.Datetime.to_string(
            datetime.combine(fields.Date.context_today(self), time.min)
        )
        now = fields.Datetime.now()

        for wc in self:
            wc.southbrook_pm_inflight_count = Wo.search_count([
                ("workcenter_id", "=", wc.id),
                ("state", "in", list(_IN_FLIGHT_WO_STATES)),
            ])
            wc.southbrook_pm_throughput_today = Wo.search_count([
                ("workcenter_id", "=", wc.id),
                ("state", "=", "done"),
                ("date_finished", ">=", today_start),
            ])
            wc.southbrook_pm_late_count = Mo.search_count([
                ("state", "not in", ["done", "cancel"]),
                ("date_deadline", "<", now),
                ("workorder_ids.workcenter_id", "=", wc.id),
            ])
            wc.southbrook_pm_equipment_alerts = Eq.search_count([
                ("workcenter_id", "=", wc.id),
                ("southbrook_condition", "in",
                 ["fair", "watch", "critical", "offline"]),
            ])
