# SPDX-License-Identifier: LGPL-3.0-only
"""MI engine snapshot tiles for MES/MPS.

``southbrook.mi.engine`` (from southbrook_manufacturing_intelligence)
is an AbstractModel. v19 raises TypeError if we try to inherit it as
``models.Model``. So we ship a concrete companion model that the MI
surface can pull tiles from.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SouthbrookMesMpsMiTiles(models.Model):
    _name = "southbrook.mes_mps.mi_tiles"
    _description = "MES/MPS Snapshot (Manufacturing Intelligence tiles)"

    label = fields.Char(default="MES/MPS Snapshot")
    mps_weeks_planned = fields.Integer(
        string="MPS Weeks Planned",
        compute="_compute_tiles",
    )
    current_bottleneck_workcenter = fields.Char(
        string="Current Bottleneck",
        compute="_compute_tiles",
    )
    current_bottleneck_load_pct = fields.Float(
        string="Bottleneck Load %",
        compute="_compute_tiles",
    )
    avg_oee_last_7d = fields.Float(
        string="Avg OEE (7d)",
        compute="_compute_tiles",
        digits=(3, 4),
    )
    workcenters_overloaded_count = fields.Integer(
        string="Overloaded Workcenters",
        compute="_compute_tiles",
    )
    mps_forecast_vs_actual_pct = fields.Float(
        string="Forecast vs Actual %",
        compute="_compute_tiles",
    )

    @api.depends("label")
    def _compute_tiles(self):
        MPS = self.env["southbrook.mes_mps.mps_period"]
        Cap = self.env["southbrook.mes_mps.workcenter_capacity"]
        OEE = self.env["southbrook.mes_mps.oee_snapshot"]
        BReport = self.env["southbrook.mes_mps.bottleneck_report"]
        today = fields.Date.context_today(self)
        last_week = today - timedelta(days=7)
        for rec in self:
            rec.mps_weeks_planned = MPS.search_count(
                [("week_start", ">=", today)]
            )
            top_report = BReport.search(
                [], order="as_of_date desc, id desc", limit=1
            )
            if top_report and top_report.top_bottleneck_workcenter_id:
                rec.current_bottleneck_workcenter = (
                    top_report.top_bottleneck_workcenter_id.display_name
                )
                rec.current_bottleneck_load_pct = (
                    top_report.top_bottleneck_load_pct
                )
            else:
                rec.current_bottleneck_workcenter = ""
                rec.current_bottleneck_load_pct = 0.0

            snaps = OEE.search([("shift_date", ">=", last_week)])
            if snaps:
                rec.avg_oee_last_7d = sum(snaps.mapped("oee")) / len(snaps)
            else:
                rec.avg_oee_last_7d = 0.0
            rec.workcenters_overloaded_count = Cap.search_count(
                [("is_overloaded", "=", True), ("week_start", ">=", last_week)]
            )
            mps_rows = MPS.search(
                [
                    ("week_start", ">=", last_week),
                    ("week_start", "<=", today),
                ]
            )
            forecast = sum(mps_rows.mapped("forecast_qty"))
            actual = sum(mps_rows.mapped("actual_demand_qty"))
            if forecast:
                rec.mps_forecast_vs_actual_pct = (actual / forecast) * 100.0
            else:
                rec.mps_forecast_vs_actual_pct = 0.0
