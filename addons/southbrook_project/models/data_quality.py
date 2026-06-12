# SPDX-License-Identifier: LGPL-3.0-only
from odoo import _, api, fields, models


ISSUE_TYPES = [
    ("blank_kitchen_project", "Blank Kitchen Project"),
    ("blank_install_due", "Blank Install Due"),
    ("placeholder_cost", "Placeholder Cost"),
    ("demo_scrap_unbuild", "Demo Scrap / Unbuild"),
    ("queue_overlap", "Queue Overlap"),
    ("equipment_count_mismatch", "Equipment Count Mismatch"),
]


class SouthbrookProjectDataQualityIssue(models.Model):
    _name = "southbrook.project.data.quality.issue"
    _description = "Southbrook Project data quality issue"
    _order = "severity desc, issue_type, model_name, res_id"

    name = fields.Char(required=True)
    issue_type = fields.Selection(ISSUE_TYPES, required=True, index=True)
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
    model_name = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    recommended_action = fields.Text(required=True)
    dry_run = fields.Boolean(default=True, readonly=True)
    state = fields.Selection(
        [
            ("new", "New"),
            ("excluded", "Excluded"),
            ("archived", "Archived"),
        ],
        default="new",
        required=True,
        index=True,
    )
    active = fields.Boolean(default=True)

    @api.model
    def _issue_key(self, issue_type, model_name, res_id):
        return [
            ("issue_type", "=", issue_type),
            ("model_name", "=", model_name),
            ("res_id", "=", res_id),
        ]

    @api.model
    def _upsert_issue(self, issue_type, record, name, recommended_action,
                      severity="warning"):
        existing = self.with_context(active_test=False).search(
            self._issue_key(issue_type, record._name, record.id),
            limit=1,
        )
        vals = {
            "name": name,
            "issue_type": issue_type,
            "severity": severity,
            "model_name": record._name,
            "res_id": record.id,
            "recommended_action": recommended_action,
            "dry_run": True,
        }
        if existing:
            existing.write(vals)
            return existing
        vals.update({
            "state": "new",
            "active": True,
        })
        return self.create(vals)

    @api.model
    def action_generate_dry_run_report(self):
        issues = self.browse()
        Task = self.env["project.task"].sudo()
        Product = self.env["product.product"].sudo()
        Workcenter = self.env["mrp.workcenter"].sudo()
        Equipment = self.env["maintenance.equipment"].sudo()

        for task in Task.search([
            ("x_southbrook_job_type", "in", ["kitchen", "vanity"]),
            ("project_id", "=", False),
        ]):
            issues |= self._upsert_issue(
                "blank_kitchen_project",
                task,
                _("Kitchen job has no Project"),
                _("Assign the job to the Kitchen Jobs project before rollout."),
                "blocker",
            )

        for task in Task.search([
            ("x_southbrook_job_type", "in", ["kitchen", "vanity"]),
            ("x_southbrook_install_due_date", "=", False),
        ]):
            issues |= self._upsert_issue(
                "blank_install_due",
                task,
                _("Kitchen or vanity job has no Install Due date"),
                _("Set Install Due before the PM daily meeting."),
            )

        for product in Product.search([
            ("default_code", "=like", "SB-%"),
            ("standard_price", "<=", 0.0),
        ]):
            issues |= self._upsert_issue(
                "placeholder_cost",
                product,
                _("Southbrook product has placeholder cost"),
                _("Update standard cost or exclude the placeholder from PM reporting."),
            )

        for model_name in ("mrp.scrap", "mrp.unbuild"):
            try:
                Model = self.env[model_name].sudo()
            except KeyError:
                continue
            for record in Model.search(["|", ("name", "ilike", "demo"),
                                        ("name", "ilike", "test")]):
                issues |= self._upsert_issue(
                    "demo_scrap_unbuild",
                    record,
                    _("Demo scrap/unbuild record is visible"),
                    _("Archive or tag the demo record before PM rollout."),
                )

        grouped_sales = {}
        for task in Task.search([("x_southbrook_sale_order_id", "!=", False)]):
            grouped_sales.setdefault(
                task.x_southbrook_sale_order_id.id,
                Task.browse(),
            )
            grouped_sales[task.x_southbrook_sale_order_id.id] |= task
        for tasks in grouped_sales.values():
            states = set(tasks.mapped("x_southbrook_readiness_state"))
            if len(tasks) > 1 and len(states) > 1:
                for task in tasks:
                    issues |= self._upsert_issue(
                        "queue_overlap",
                        task,
                        _("Same sales order appears in multiple PM queues"),
                        _("Merge duplicate Project jobs or pick one PM owner."),
                    )

        equipment_field = "workcenter_id" if "workcenter_id" in Equipment._fields else False
        if equipment_field:
            for workcenter in Workcenter.search([("active", "=", True)]):
                count = Equipment.search_count([(equipment_field, "=", workcenter.id)])
                if count == 0:
                    issues |= self._upsert_issue(
                        "equipment_count_mismatch",
                        workcenter,
                        _("Work center has no linked equipment"),
                        _("Link maintenance equipment or mark the work center out of scope."),
                    )

        return issues

    def action_exclude_from_pm_reporting(self):
        self.write({"state": "excluded"})
        return True

    def action_archive_issue(self):
        self.write({"state": "archived", "active": False})
        return True
