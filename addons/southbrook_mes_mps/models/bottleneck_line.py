# SPDX-License-Identifier: LGPL-3.0-only
"""Bottleneck report line — one row per workcenter."""
from odoo import fields, models


class SouthbrookMesMpsBottleneckLine(models.Model):
    _name = "southbrook.mes_mps.bottleneck_line"
    _description = "Bottleneck Report Line"
    _order = "bottleneck_score desc"

    report_id = fields.Many2one(
        "southbrook.mes_mps.bottleneck_report",
        string="Report",
        required=True,
        ondelete="cascade",
    )
    workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="Work Center",
        required=True,
        ondelete="cascade",
    )
    load_pct = fields.Float(string="Load %")
    bottleneck_score = fields.Float(
        string="Bottleneck Score",
        help="load_pct × downstream-dependency count.",
    )
    recommended_action = fields.Selection(
        [
            ("add_shift", "Add Shift"),
            ("outsource", "Outsource"),
            ("split_order", "Split Order"),
            ("no_action", "No Action"),
        ],
        string="Recommended Action",
        default="no_action",
    )
