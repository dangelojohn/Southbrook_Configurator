# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models


class SouthbrookProjectReadinessLine(models.Model):
    _name = "southbrook.project.readiness.line"
    _description = "Southbrook Project Readiness Line"
    _order = "task_id, sequence, id"

    task_id = fields.Many2one(
        "project.task",
        string="Kitchen Job",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10, index=True)
    check_key = fields.Selection(
        [
            ("data", "Data Completeness"),
            ("cabinet_specs", "Cabinet Specs"),
            ("production_release", "Production Release Checklist"),
            ("mrp", "MRP Link"),
            ("engineering", "Engineering / CAD"),
            ("materials", "Materials / Purchasing"),
            ("scheduling", "Scheduling"),
            ("crew", "Crew"),
            ("equipment", "Equipment / Tooling"),
            ("capacity", "Production Capacity"),
            ("install", "Delivery / Install"),
            ("calculations", "Calculations"),
            ("stage_mismatch", "PM Phase / Manufacturing Reality"),
        ],
        required=True,
        index=True,
    )
    name = fields.Char(required=True)
    status = fields.Selection(
        [
            ("ready", "Ready"),
            ("review", "Review"),
            ("blocked", "Blocked"),
            ("info", "Info"),
        ],
        required=True,
        default="info",
        index=True,
    )
    severity = fields.Selection(
        [
            ("info", "Info"),
            ("warning", "Warning"),
            ("blocker", "Blocker"),
        ],
        required=True,
        default="info",
        index=True,
    )
    reason = fields.Char(required=True)
    evidence = fields.Text()
    recommended_action = fields.Text()

    project_id = fields.Many2one(
        related="task_id.project_id",
        store=True,
        readonly=True,
    )
    source_order_id = fields.Many2one(
        related="task_id.source_order_id",
        store=True,
        readonly=True,
    )
    customer_id = fields.Many2one(
        related="task_id.customer_id",
        store=True,
        readonly=True,
    )
