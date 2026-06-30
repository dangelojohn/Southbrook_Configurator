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
        if not self._southbrook_has_manufacturable_line():
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

    def _southbrook_has_manufacturable_line(self):
        """True iff at least one order line resolves to a real, normal-type
        BoM — the same definition `southbrook_mrp_pm` uses when actually
        cutting MOs (`_resolve_bom_for_line` / `action_send_to_production`).

        R3 PR #27 fix (2026-06-30): the prior check —
            mrp.bom.search_count([('product_tmpl_id', 'in', tmpl_ids)])
        — was over-broad in three ways and was spawning empty
        project.task records in prod for non-manufacturing sales
        (service-only, refacing-deposit, freight-only orders):

        1. It accepted ANY BoM type (kit/phantom matched as well as
           normal). A phantom BoM means "explode at sale", not
           "manufacture", so it should not trigger a job.
        2. It didn't honour variant-specific BoMs — `_bom_find` would
           pick a more specific match (or none), but a raw template
           search ignored that resolution.
        3. It didn't filter by company, so multi-company DBs would
           match a sibling company's BoM and create a cross-company
           job task.

        Reusing `_resolve_bom_for_line` (sibling-class @staticmethod on
        the unified SaleOrder, contributed by southbrook_mrp_pm — which
        we already depend on) ties this gate to the same predicate that
        downstream MO-creation actually uses. If `_resolve_bom_for_line`
        is somehow absent (defensive — e.g. southbrook_mrp_pm uninstalled
        in a custom deployment), fall back to a normal-type search so we
        still err on the side of "only spawn for true manufacturing
        sales".
        """
        self.ensure_one()
        Bom = self.env["mrp.bom"].sudo()
        resolver = getattr(self, "_resolve_bom_for_line", None)
        for line in self.order_line:
            if not line.product_id:
                continue
            if getattr(line, "display_type", False):
                # section / note lines — never manufacturable.
                continue
            if resolver is not None:
                bom = resolver(Bom, line)
            else:
                bom = Bom.search(
                    [
                        "|",
                        ("product_id", "=", line.product_id.id),
                        "&",
                        ("product_id", "=", False),
                        ("product_tmpl_id", "=",
                         line.product_id.product_tmpl_id.id),
                        ("type", "=", "normal"),
                    ],
                    order="sequence, id",
                    limit=1,
                )
            if bom:
                return True
        return False

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
