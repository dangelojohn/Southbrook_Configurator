# SPDX-License-Identifier: LGPL-3.0-only
"""southbrook.shop.daily — pre-aggregated daily shop snapshot.

W048 (R7.4, 2026-06-27)
=======================

JTBD: "When the GM asks for actual-vs-plan rollup at month end, I
want a pre-aggregated daily snapshot table I can pivot from — not
recomputing 30 days of MOs every time."

The classic month-end report rebuilds these aggregates from raw
mrp.production / mrp.workorder / southbrook.kitchen.workcenter.downtime
data on every open. With 8-12 work centers x 30 days that is fine for
one user, ugly for ten concurrent.

This model snapshots one row per (workcenter x date). The cron at
23:55 takes today's slice; the rebuild server action repaints a
horizon window for backfill / corrections.

Carried metrics:
  hours_loaded         sum of duration_expected for WOs scheduled here
  hours_actual         sum of duration for WOs that actually ran here
  mo_completed_count   count of MOs that hit state=done with this WC
                       in their routing
  scrap_qty_total      sum of stock.scrap.scrap_qty closed today and
                       linked to a WO at this WC
  defect_count         count of southbrook.mi.check rows created today
                       on a WO at this WC
  downtime_minutes     sum of southbrook.kitchen.workcenter.downtime
                       duration_min closed today at this WC

Idempotency
-----------
The cron + rebuild both DELETE-then-CREATE the affected (WC, date)
tuples. Re-running the same day is therefore a safe no-op (the row
content is the same after the rebuild).

Constraints
-----------
- No raw SQL. Pure ORM (read_group + browse).
- Cron is the only writer in steady state; rebuild action is the
  manual escape hatch for backfilling history.
"""
import logging
from datetime import date, datetime, time, timedelta

from odoo import _, api, fields, models


_logger = logging.getLogger(__name__)


# Default backfill window when the rebuild action is invoked from the
# list view (no horizon kwarg). 30 days = the GM's monthly cadence.
DEFAULT_REBUILD_HORIZON_DAYS = 30


class SouthbrookShopDaily(models.Model):
    _name = "southbrook.shop.daily"
    _description = "Daily shop snapshot per (workcenter x date)"
    _order = "date desc, workcenter_id asc"
    _rec_name = "display_name"

    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        required=True,
        ondelete="cascade",
        index=True,
    )
    date = fields.Date(
        string="Day",
        required=True,
        index=True,
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    hours_loaded = fields.Float(
        string="Hours Loaded",
        help="Sum of mrp.workorder.duration_expected (minutes / 60) "
             "for WOs scheduled at this WC on this day.",
    )
    hours_actual = fields.Float(
        string="Hours Actual",
        help="Sum of mrp.workorder.duration (minutes / 60) for WOs at "
             "this WC whose date_finished landed on this day.",
    )
    mo_completed_count = fields.Integer(
        string="MOs Completed",
        help="Count of mrp.production rows that hit state=done on this "
             "day with at least one WO at this WC. A multi-station MO "
             "is double-counted across all its WCs by design — this "
             "table is per-station throughput, not per-MO.",
    )
    scrap_qty_total = fields.Float(
        string="Scrap Qty",
        help="Sum of stock.scrap.scrap_qty rows whose workorder_id is "
             "at this WC and whose validation landed on this day.",
    )
    defect_count = fields.Integer(
        string="Defects",
        help="Count of southbrook.mi.check rows created on this day "
             "with x_sbk_workorder_id at this WC.",
    )
    downtime_minutes = fields.Float(
        string="Downtime (min)",
        help="Sum of southbrook.kitchen.workcenter.downtime "
             "duration_min for rows whose date_start landed on this "
             "day at this WC.",
    )

    refreshed_at = fields.Datetime(
        string="Refreshed",
        default=fields.Datetime.now,
        readonly=True,
        help="When the cron / rebuild last touched this row.",
    )

    # Odoo 19 unique constraint primitive — see memory
    # odoo19_sql_constraints_deprecated.
    _unique_shop_daily = models.Constraint(
        "UNIQUE(workcenter_id, date)",
        "Only one shop daily row per work-center per day.",
    )

    @api.depends("workcenter_id.name", "date")
    def _compute_display_name(self):
        for row in self:
            row.display_name = "%s — %s" % (
                row.workcenter_id.display_name or "?",
                row.date and fields.Date.to_string(row.date) or "?",
            )

    # ------------------------------------------------------------------
    # Cron entry — snapshot today's slice for every active WC
    # ------------------------------------------------------------------
    @api.model
    def _cron_snapshot_today(self):
        """Daily 23:55 cron — snapshot the day that is closing.

        Idempotent: deletes the (today, every active WC) tuples first
        then re-creates from the source tables. Re-running the same
        day is a no-op (the content is the same).
        """
        today = fields.Date.context_today(self)
        return self._snapshot_for_window(today, today)

    @api.model
    def action_rebuild_history(self, horizon_days=None):
        """Server-action entry — rebuild the last `horizon_days` days
        for every active WC. Default = 30 days for the GM month-end
        report. Idempotent."""
        horizon = horizon_days or DEFAULT_REBUILD_HORIZON_DAYS
        today = fields.Date.context_today(self)
        start = today - timedelta(days=horizon - 1)
        rows = self._snapshot_for_window(start, today)
        # Surface a notification so the operator sees the run finished.
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Shop snapshot rebuilt"),
                "message": _("Rebuilt %(rows)d rows across %(days)d days.") % {
                    "rows": len(rows), "days": horizon,
                },
                "type": "success",
                "sticky": False,
            },
        }

    # ------------------------------------------------------------------
    # Core builder — used by both cron + rebuild
    # ------------------------------------------------------------------
    @api.model
    def _snapshot_for_window(self, start_date, end_date):
        """Rebuild rows for [start_date, end_date] inclusive for every
        active mrp.workcenter. Pure ORM — no SQL. Deletes first then
        creates, so re-runs are safe.
        """
        if not isinstance(start_date, date):
            start_date = fields.Date.to_date(start_date)
        if not isinstance(end_date, date):
            end_date = fields.Date.to_date(end_date)
        if start_date > end_date:
            return self.browse()

        workcenters = self.env["mrp.workcenter"].search([
            ("active", "=", True),
        ])
        if not workcenters:
            return self.browse()

        # 1) Drop the existing window for idempotency.
        existing = self.search([
            ("workcenter_id", "in", workcenters.ids),
            ("date", ">=", start_date),
            ("date", "<=", end_date),
        ])
        if existing:
            existing.unlink()

        # 2) Walk the day list once. For each day pull the day's
        #    sources from each table, bucket by WC in py. Avoids
        #    read_group's day-bucket string-parse fragility (the
        #    same pattern southbrook.capacity.day uses).
        creates = []
        n_days = (end_date - start_date).days + 1
        for offset in range(n_days):
            d = start_date + timedelta(days=offset)
            day_start = datetime.combine(d, time.min)
            day_end = datetime.combine(d + timedelta(days=1), time.min)

            loaded_map = self._pull_loaded_hours(workcenters, day_start, day_end)
            actual_map = self._pull_actual_hours(workcenters, day_start, day_end)
            mo_done_map = self._pull_mo_completed(workcenters, day_start, day_end)
            scrap_map = self._pull_scrap(workcenters, day_start, day_end)
            defect_map = self._pull_defects(workcenters, day_start, day_end)
            downtime_map = self._pull_downtime(workcenters, day_start, day_end)

            for wc in workcenters:
                creates.append({
                    "workcenter_id": wc.id,
                    "date": d,
                    "hours_loaded": loaded_map.get(wc.id, 0.0),
                    "hours_actual": actual_map.get(wc.id, 0.0),
                    "mo_completed_count": mo_done_map.get(wc.id, 0),
                    "scrap_qty_total": scrap_map.get(wc.id, 0.0),
                    "defect_count": defect_map.get(wc.id, 0),
                    "downtime_minutes": downtime_map.get(wc.id, 0.0),
                })
        rows = self.create(creates) if creates else self.browse()
        _logger.info(
            "W048: shop_daily snapshot rebuilt %d rows for window "
            "%s..%s across %d WCs",
            len(rows), start_date, end_date, len(workcenters),
        )
        return rows

    # ------------------------------------------------------------------
    # Source pulls — each returns {workcenter_id: aggregate}
    # ------------------------------------------------------------------
    def _pull_loaded_hours(self, workcenters, day_start, day_end):
        """Loaded minutes: WOs whose date_start landed in the day,
        across ALL states. Converted to hours."""
        Workorder = self.env["mrp.workorder"]
        wos = Workorder.search([
            ("workcenter_id", "in", workcenters.ids),
            ("date_start", ">=", day_start),
            ("date_start", "<", day_end),
        ])
        out = {}
        for wo in wos:
            mins = wo.duration_expected or 0.0
            out[wo.workcenter_id.id] = out.get(wo.workcenter_id.id, 0.0) + (mins / 60.0)
        return out

    def _pull_actual_hours(self, workcenters, day_start, day_end):
        """Actual minutes: WOs whose date_finished landed in the day.
        Converted to hours."""
        Workorder = self.env["mrp.workorder"]
        wos = Workorder.search([
            ("workcenter_id", "in", workcenters.ids),
            ("date_finished", ">=", day_start),
            ("date_finished", "<", day_end),
        ])
        out = {}
        for wo in wos:
            mins = wo.duration or 0.0
            out[wo.workcenter_id.id] = out.get(wo.workcenter_id.id, 0.0) + (mins / 60.0)
        return out

    def _pull_mo_completed(self, workcenters, day_start, day_end):
        """Count of done MOs in the day, attributed to every WC their
        WOs touched. A multi-station MO is double-counted across all
        WCs — by design (this table is per-station throughput).
        """
        Production = self.env["mrp.production"]
        mos = Production.search([
            ("state", "=", "done"),
            ("date_finished", ">=", day_start),
            ("date_finished", "<", day_end),
        ])
        out = {}
        for mo in mos:
            seen = set()
            for wo in mo.workorder_ids:
                wc_id = wo.workcenter_id.id
                if not wc_id or wc_id in seen:
                    continue
                if wc_id not in workcenters.ids:
                    continue
                seen.add(wc_id)
                out[wc_id] = out.get(wc_id, 0) + 1
        return out

    def _pull_scrap(self, workcenters, day_start, day_end):
        """Sum of validated stock.scrap.scrap_qty in the day, bucketed
        by the workorder_id's workcenter_id."""
        Scrap = self.env["stock.scrap"]
        # Done state is the validated marker on stock.scrap.
        scraps = Scrap.search([
            ("state", "=", "done"),
            ("workorder_id", "!=", False),
            ("write_date", ">=", day_start),
            ("write_date", "<", day_end),
        ])
        out = {}
        for s in scraps:
            wc_id = s.workorder_id.workcenter_id.id
            if not wc_id or wc_id not in workcenters.ids:
                continue
            out[wc_id] = out.get(wc_id, 0.0) + (s.scrap_qty or 0.0)
        return out

    def _pull_defects(self, workcenters, day_start, day_end):
        """Count of mi.check rows created in the day with WC linkage.

        Feature-detect southbrook.mi.check + its x_sbk_workorder_id
        column — this addon ships in southbrook_mrp_pm which depends
        only on PLM, not on southbrook_manufacturing_intelligence /
        southbrook_mrp_kitchen_workcenters. When the upstream defect
        surface isn't installed we return an empty map (zero defects)
        rather than break the snapshot.
        """
        if "southbrook.mi.check" not in self.env:
            return {}
        Check = self.env["southbrook.mi.check"]
        if "x_sbk_workorder_id" not in Check._fields:
            return {}
        checks = Check.search([
            ("create_date", ">=", day_start),
            ("create_date", "<", day_end),
            ("x_sbk_workorder_id", "!=", False),
        ])
        out = {}
        for c in checks:
            wc_id = c.x_sbk_workorder_id.workcenter_id.id
            if not wc_id or wc_id not in workcenters.ids:
                continue
            out[wc_id] = out.get(wc_id, 0) + 1
        return out

    def _pull_downtime(self, workcenters, day_start, day_end):
        """Sum of downtime duration_min for rows whose date_start
        landed in the day at the WC.

        Feature-detect southbrook.kitchen.workcenter.downtime — see
        _pull_defects rationale. Returns empty map when the upstream
        downtime surface isn't installed.
        """
        if "southbrook.kitchen.workcenter.downtime" not in self.env:
            return {}
        Downtime = self.env["southbrook.kitchen.workcenter.downtime"]
        rows = Downtime.search([
            ("workcenter_id", "in", workcenters.ids),
            ("date_start", ">=", day_start),
            ("date_start", "<", day_end),
        ])
        out = {}
        for r in rows:
            out[r.workcenter_id.id] = out.get(r.workcenter_id.id, 0.0) + (r.duration_min or 0.0)
        return out
