# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SouthbrookProjectDataQualityReport(models.TransientModel):
    _name = "southbrook.project.data.quality.report"
    _description = "Southbrook Project Data Quality Dry Run"
    _order = "id desc"

    name = fields.Char(default="Southbrook Data Quality Dry Run", required=True)
    project_id = fields.Many2one("project.project", string="Project", readonly=True)
    generated_at = fields.Datetime(
        string="Generated At", default=fields.Datetime.now, readonly=True)
    summary = fields.Text(readonly=True)
    line_ids = fields.One2many(
        "southbrook.project.data.quality.line",
        "report_id",
        string="Dry-Run Findings",
        readonly=True,
    )


class SouthbrookProjectDataQualityLine(models.TransientModel):
    _name = "southbrook.project.data.quality.line"
    _description = "Southbrook Project Data Quality Finding"
    _order = "severity desc, issue_key, id"

    report_id = fields.Many2one(
        "southbrook.project.data.quality.report",
        required=True,
        ondelete="cascade",
    )
    issue_key = fields.Selection(
        [
            ("blank_kitchen_project", "Blank Kitchen Project"),
            ("missing_install_due", "Missing Install Due"),
            ("placeholder_estimated_cost", "Placeholder Estimated Cost"),
            ("demo_scrap_unbuild", "Demo Scrap / Unbuild"),
            ("queue_overlap", "Queue Overlap"),
            ("equipment_count_mismatch", "Equipment Count Mismatch"),
        ],
        required=True,
        index=True,
    )
    severity = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("blocker", "Blocker"),
        ],
        default="warning",
        required=True,
        index=True,
    )
    model_name = fields.Char(required=True, readonly=True)
    record_ref = fields.Char(readonly=True)
    reason = fields.Char(required=True, readonly=True)
    recommended_action = fields.Text(readonly=True)
