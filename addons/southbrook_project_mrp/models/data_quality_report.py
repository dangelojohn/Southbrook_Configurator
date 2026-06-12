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
    res_model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    record_ref = fields.Char(readonly=True)
    reason = fields.Char(required=True, readonly=True)
    recommended_action = fields.Text(readonly=True)
    cleanup_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("applied", "Applied"),
            ("skipped", "Manual"),
        ],
        default="pending",
        required=True,
        readonly=True,
    )
    cleanup_note = fields.Text(readonly=True)

    def action_apply_safe_cleanup(self):
        for line in self:
            record = line._southbrook_cleanup_record()
            if (
                line.issue_key == "demo_scrap_unbuild"
                and record
                and "southbrook_exclude_from_pm_reports" in record._fields
            ):
                record.write({
                    "southbrook_exclude_from_pm_reports": True,
                    "southbrook_cleanup_note": (
                        "Excluded from Southbrook PM reports by data-quality "
                        "dry-run cleanup. Original finding: %s"
                        % (line.reason or "")
                    ),
                })
                line.cleanup_state = "applied"
                line.cleanup_note = (
                    "Record was tagged for exclusion from Southbrook PM "
                    "reports. No data was deleted.")
            else:
                line.cleanup_state = "skipped"
                line.cleanup_note = (
                    "Manual review required. This dry-run cleanup does not "
                    "modify operational data for this finding.")
        return True

    def _southbrook_cleanup_record(self):
        self.ensure_one()
        model = self.res_model or self.model_name
        if not model or model not in self.env or not self.res_id:
            return self.env["ir.model"].browse()
        return self.env[model].browse(self.res_id).exists()
