# SPDX-License-Identifier: LGPL-3.0-only
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self:
            order._southbrook_ensure_job()
        return res

    def _southbrook_ensure_job(self):
        """Create (once) the project.task customer-job for a manufacturing
        order and attach any MOs already created for it. MOs created later by
        procurement back-link themselves (see mrp.production.create)."""
        self.ensure_one()
        tmpl_ids = self.order_line.product_id.product_tmpl_id.ids
        drives_manufacturing = bool(tmpl_ids) and bool(
            self.env["mrp.bom"].search_count(
                [("product_tmpl_id", "in", tmpl_ids)]))
        if not drives_manufacturing:
            return False

        Task = self.env["project.task"]
        # Use southbrook_project's x_southbrook_sale_order_id (guaranteed by our
        # dependency) rather than sale_project's sale_order_id (not a dep, and
        # we don't want its auto service-task creation).
        task = Task.search(
            [("x_southbrook_sale_order_id", "=", self.id)], limit=1)
        if not task:
            project = self._southbrook_job_project()
            if not project:
                return False
            task = Task.create({
                "name": "Job: %s — %s" % (self.name, self.partner_id.name or ""),
                "project_id": project.id,
                "x_southbrook_sale_order_id": self.id,
            })

        mos = self.env["mrp.production"].search([
            ("sale_line_id.order_id", "=", self.id),
            ("project_task_id", "=", False),
        ])
        mos.write({"project_task_id": task.id})
        return task

    def _southbrook_job_project(self):
        """Target project for new jobs: ir.config_parameter override, else the
        first project (does not create one — honours the no-config guardrail)."""
        Project = self.env["project.project"]
        param = self.env["ir.config_parameter"].sudo().get_param(
            "southbrook_project_mrp.job_project_id")
        if param:
            proj = Project.browse(int(param)).exists()
            if proj:
                return proj
        return Project.search([], limit=1, order="id")
