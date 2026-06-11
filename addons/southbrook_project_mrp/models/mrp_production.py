# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    project_task_id = fields.Many2one(
        "project.task",
        string="Customer Job",
        index=True,
        copy=False,
        help="The Project task (customer job) this Manufacturing Order is "
             "part of. A job typically spans several MOs — base cabinet, "
             "worktop, pantry — all rolled up under one task for the PM.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Procurement often creates the MO AFTER the sale is confirmed (and the
        # job task created), so back-link any new MO that traces to a sale
        # order which already has a job. Manual MOs are linked by hand / the
        # task's "Link MOs" action.
        productions = super().create(vals_list)
        for mo in productions:
            if mo.project_task_id or not mo.sale_line_id:
                continue
            task = self.env["project.task"].search(
                [("x_southbrook_sale_order_id", "=",
                  mo.sale_line_id.order_id.id)], limit=1)
            if task:
                mo.project_task_id = task.id
        return productions
