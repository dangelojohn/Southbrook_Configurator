# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.routing.workcenter — operation-template binding.

Lets a BoM operation pick a southbrook.kitchen.operation.template so
the kitchen-formula duration in M2 can replace Odoo's flat
`time_cycle` estimate.

Bound via a Many2one on the BoM-operation row itself rather than on
the work-center, because the same work center serves multiple
operations (the cutting station handles both rough-cut and
panel-rip with very different time-per-unit factors).

The M3 stub in mrp_workorder._sbk_kitchen_operation_template reads
this field via hasattr; M4 lights it up.
"""
from odoo import fields, models


class MrpRoutingWorkcenter(models.Model):
    _inherit = "mrp.routing.workcenter"

    x_sbk_operation_template_id = fields.Many2one(
        "southbrook.kitchen.operation.template",
        string="Kitchen Operation Template",
        ondelete="set null",
        index=True,
        help="When set, the M2 duration formula on the template "
             "drives x_sbk_kitchen_expected_min on each work order "
             "generated from this routing line. Native time_cycle stays "
             "unchanged — the planner can compare the two engines.",
    )
    x_sbk_driver_override = fields.Float(
        string="Driver Override",
        digits=(10, 2),
        help="Optional override for the quantity driver fed into the "
             "template's compute_expected_duration. When 0 (default), "
             "the driver is pulled from production_id.product_qty (or "
             "0 for fixed-mode templates).",
    )
