# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SouthbrookProjectJobTemplate(models.Model):
    _name = "southbrook.project.job.template"
    _description = "Southbrook Project Job Template"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    job_type = fields.Selection(
        [
            ("full_kitchen", "Full Kitchen"),
            ("vanity", "Vanity"),
            ("pantry", "Pantry"),
            ("repair", "Repair"),
            ("warranty", "Warranty / Remake"),
            ("single_cabinet", "Custom Single Cabinet"),
            ("worktop", "Worktop"),
        ],
        required=True,
        index=True,
    )
    typical_cabinet_families = fields.Char(
        help="Cabinet families normally expected for this job type.")
    required_specs = fields.Text(
        help="Structured specs the PM should confirm before release.")
    release_checklist = fields.Text(
        help="Release checklist focus for this job type.")
    line_ids = fields.One2many(
        "southbrook.project.job.template.line",
        "template_id",
        string="Milestones / Subtasks",
        copy=True,
    )


class SouthbrookProjectJobTemplateLine(models.Model):
    _name = "southbrook.project.job.template.line"
    _description = "Southbrook Project Job Template Line"
    _order = "template_id, sequence, id"

    template_id = fields.Many2one(
        "southbrook.project.job.template",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    description = fields.Text()
