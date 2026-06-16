# SPDX-License-Identifier: LGPL-3.0-only
"""
mrp.planning.run cron extension — weekly planning baseline.

Phase 1.2 of Southbrook Premium MRP Orchestration. This file adds the
``_cron_baseline`` classmethod entry point referenced by
``data/ir_cron.xml`` for "Southbrook: Weekly Planning Baseline".

NF1 carve-out: this file does NOT count against the 7-routine custom
register. It is a thin cron entry point that:

  * de-duplicates against an already-open run from the last 24h
  * creates a single new ``mrp.planning.run`` record
  * optionally invokes ``action_run`` when present on the underlying
    OpenValue engine

There is no business math, no decisioning. If a sibling agent extends
the planning engine itself, that work lives in the OpenValue addon —
not here.

OpenValue engine (``openvalue_mrp_planning_engine``) gives us:
    name, date, company_id, warehouse_id, state, line_ids, action_run()

Downstream OpenValue addons layer on additional fields the brief calls
out (capacity_horizon_days, include_sales_demand, multilevel,
overloaded_workcenter_count). We pass those via ``hasattr`` checks so
the cron stays installable whether or not every OpenValue layer is in
the database.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class MrpPlanningRun(models.Model):
    _inherit = "mrp.planning.run"

    @api.model
    def _cron_baseline(self):
        """Create and launch a weekly planning baseline run.

        Idempotent within a 24h window: if a planning run already
        exists from the last day, the cron logs and exits without
        creating a duplicate.

        Defensive: any error during ``action_run`` is logged as a
        warning so the cron stays green and self-heals next interval.
        """
        cutoff = fields.Datetime.now() - timedelta(hours=24)
        recent = self.search(
            [("create_date", ">=", fields.Datetime.to_string(cutoff))],
            limit=1,
        )
        if recent:
            _logger.info(
                "Southbrook planning baseline: run %s exists within "
                "24h window, skipping.",
                recent.name,
            )
            return recent

        vals = {"date": fields.Date.today()}
        # Optional fields, contributed by downstream OpenValue addons.
        # Probe with ``hasattr`` so the cron stays installable even
        # when only the base ``openvalue_mrp_planning_engine`` is on.
        optional_defaults = {
            "capacity_horizon_days": 14,
            "include_sales_demand": True,
            "multilevel": False,
        }
        for fname, fvalue in optional_defaults.items():
            if fname in self._fields:
                vals[fname] = fvalue

        try:
            run = self.create(vals)
        except Exception as exc:  # noqa: BLE001 — cron must stay green
            _logger.warning(
                "Southbrook planning baseline: create failed (%s) — "
                "cron will retry next week.",
                exc,
            )
            return self.browse()

        if hasattr(run, "action_run"):
            try:
                run.action_run()
            except Exception as exc:  # noqa: BLE001 — log and continue
                _logger.warning(
                    "Southbrook planning baseline: action_run failed "
                    "on %s (%s) — leaving run in draft for manual "
                    "inspection.",
                    run.name,
                    exc,
                )
        else:
            _logger.info(
                "Southbrook planning baseline: %s created in draft "
                "(no action_run method available on this build).",
                run.name,
            )
        return run
