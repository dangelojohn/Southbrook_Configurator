# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.production — kitchen-project linkage + roll-up totals.

Adds the planner-facing context the kitchen shop floor needs that
upstream Odoo MRP doesn't carry: which kitchen project / room /
customer-facing cabinet the MO is producing, the install due date
the customer is holding us to, a complexity_factor that flows
into the M2 duration formula, and rolled-up estimated / actual /
variance minutes summed across the MO's work orders.

The x_sbk_kitchen_project_id reuses sb.kitchen.project from
southbrook_kitchen_workspace per the locked decision in the M0
discovery (no parallel project model).
"""
from odoo import api, fields, models


PRIORITY_LEVELS = [
    ("urgent", "Urgent (rush)"),
    ("high", "High"),
    ("normal", "Normal"),
    ("low", "Low"),
]


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    x_sbk_kitchen_project_id = fields.Many2one(
        "sb.kitchen.project",
        string="Kitchen Project",
        index=True,
        tracking=True,
        help="The Southbrook kitchen project this MO is producing for. "
             "Reuses sb.kitchen.project from southbrook_kitchen_workspace.",
    )
    x_sbk_kitchen_room = fields.Char(
        string="Room / Zone",
        tracking=True,
        help="Free-text room label (e.g. 'Kitchen', 'Island', 'Pantry', "
             "'Master Bath'). Free-text rather than enum because every "
             "project's room map is different.",
    )
    x_sbk_cabinet_code = fields.Char(
        string="Cabinet Code",
        tracking=True,
        help="Customer-facing cabinet identifier (e.g. 'B30', 'W2430', "
             "'TP3084'). Shown on the spec sheet and shop copy.",
    )
    x_sbk_install_due_date = fields.Date(
        string="Install Due",
        tracking=True,
        help="The date the customer expects on-site install. Drives "
             "scheduling priority — distinct from Odoo's date_planned "
             "which is the production start date.",
    )
    x_sbk_complexity_factor = fields.Float(
        string="Complexity Factor",
        default=1.0,
        digits=(4, 2),
        help="Multiplier flowed into the operation-template duration "
             "formula. 1.00 = standard. 1.25 = e.g. ornate moulding + "
             "non-standard finish. 0.85 = simple slab construction. "
             "Operates on the per-unit portion only; setup / changeover "
             "are unaffected.",
    )
    x_sbk_priority_level = fields.Selection(
        PRIORITY_LEVELS,
        string="Kitchen Priority",
        default="normal",
        tracking=True,
        help="Southbrook-specific priority. Distinct from upstream "
             "priority — that one drives Odoo's scheduler; this one "
             "drives the shop-floor sort order.",
    )

    # ------------------------------------------------------------------
    # Rolled-up workorder metrics
    # ------------------------------------------------------------------
    x_sbk_total_estimated_min = fields.Float(
        string="Total Estimated (min)",
        compute="_compute_x_sbk_totals",
        store=True,
        digits=(10, 2),
    )
    x_sbk_total_actual_min = fields.Float(
        string="Total Actual (min)",
        compute="_compute_x_sbk_totals",
        store=True,
        digits=(10, 2),
    )
    x_sbk_total_variance_min = fields.Float(
        string="Total Variance (min)",
        compute="_compute_x_sbk_totals",
        store=True,
        digits=(10, 2),
        help="actual − estimated. Positive = over budget.",
    )

    @api.depends(
        "workorder_ids.x_sbk_kitchen_expected_min",
        "workorder_ids.duration",
    )
    def _compute_x_sbk_totals(self):
        for mo in self:
            est = sum(mo.workorder_ids.mapped("x_sbk_kitchen_expected_min"))
            act = sum(mo.workorder_ids.mapped("duration"))
            mo.x_sbk_total_estimated_min = est
            mo.x_sbk_total_actual_min = act
            mo.x_sbk_total_variance_min = act - est

    def action_sbk_recalc_all_workorder_durations(self):
        """Bulk recompute kitchen-formula expected duration across all
        of this MO's work orders. The per-WO button handles a single
        operation; this one is for the planner who just changed the
        complexity factor and wants every operation re-estimated at
        once."""
        for mo in self:
            mo.workorder_ids.action_sbk_recalc_kitchen_duration()
        return True
