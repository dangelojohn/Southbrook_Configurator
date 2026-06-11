# SPDX-License-Identifier: LGPL-3.0-only
"""mrp.workorder — kitchen-specific costing extensions.

Native Odoo 19 fields already cover the basics:
  duration            actual minutes worked
  duration_expected   expected minutes (Odoo's own)
  costs_hour          hourly cost from workcenter
  direct_cost         actual cost from Odoo's compute
  duration_percent    actual vs expected ratio

This module adds Southbrook-specific fields per brief §13 that the
kitchen reports need but Odoo doesn't:

  x_sbk_kitchen_expected_min   what the operation-template formula
                               produced (parallel to Odoo's
                               duration_expected; kept separate so
                               the planner can audit which engine
                               produced which number)
  x_sbk_variance_min           actual − x_sbk_kitchen_expected_min
  x_sbk_estimated_cost         x_sbk_kitchen_expected_min × hourly
  x_sbk_actual_cost            duration × hourly (mirrors direct_cost
                               but reads costs_hour from THE work
                               center, not whatever Odoo's compute
                               cached — useful when rates changed
                               mid-run)
  x_sbk_cost_variance          actual − estimated
  x_sbk_rework_count           # of rework checks tied to this WO
  x_sbk_rework_cost            cost contribution from rework
                               work orders linked back via
                               x_sbk_rework_workorder_id on the
                               mi.check
  x_sbk_downtime_min           sum of attached downtime durations
  x_sbk_downtime_cost          sum of attached downtime costs
"""
from odoo import api, fields, models


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    # ------------------------------------------------------------------
    # Duration variance (M2 formula vs native expected)
    # ------------------------------------------------------------------
    x_sbk_kitchen_expected_min = fields.Float(
        string="Kitchen Expected (min)",
        help="Expected duration as computed by the operation-template "
             "duration formula. Parallel to Odoo's duration_expected "
             "so the planner can audit which estimate came from which "
             "engine.",
    )
    x_sbk_variance_min = fields.Float(
        string="Variance (min)",
        compute="_compute_x_sbk_variance",
        store=True,
        help="duration − x_sbk_kitchen_expected_min. Positive = over "
             "budget; negative = under.",
    )

    # ------------------------------------------------------------------
    # Costing fields
    # ------------------------------------------------------------------
    x_sbk_estimated_cost = fields.Float(
        string="Estimated Cost",
        compute="_compute_x_sbk_costs",
        store=True,
        digits="Product Price",
    )
    x_sbk_actual_cost = fields.Float(
        string="Actual Cost",
        compute="_compute_x_sbk_costs",
        store=True,
        digits="Product Price",
    )
    x_sbk_cost_variance = fields.Float(
        string="Cost Variance",
        compute="_compute_x_sbk_costs",
        store=True,
        digits="Product Price",
    )

    # ------------------------------------------------------------------
    # Rework metrics (rolls up southbrook.mi.check records)
    # ------------------------------------------------------------------
    x_sbk_rework_count = fields.Integer(
        string="Rework Checks",
        compute="_compute_x_sbk_rework_metrics",
        store=False,
    )
    x_sbk_rework_cost = fields.Float(
        string="Rework Cost",
        compute="_compute_x_sbk_rework_metrics",
        store=False,
        digits="Product Price",
        help="Sum of duration cost across rework work orders that "
             "trace back to this WO via x_sbk_rework_workorder_id on "
             "southbrook.mi.check records.",
    )

    # ------------------------------------------------------------------
    # Downtime aggregates
    # ------------------------------------------------------------------
    x_sbk_downtime_min = fields.Float(
        string="Downtime (min)",
        compute="_compute_x_sbk_downtime",
        store=False,
    )
    x_sbk_downtime_cost = fields.Float(
        string="Downtime Cost",
        compute="_compute_x_sbk_downtime",
        store=False,
        digits="Product Price",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("duration", "x_sbk_kitchen_expected_min")
    def _compute_x_sbk_variance(self):
        for wo in self:
            wo.x_sbk_variance_min = (
                (wo.duration or 0.0) - (wo.x_sbk_kitchen_expected_min or 0.0)
            )

    @api.depends("duration", "x_sbk_kitchen_expected_min",
                 "workcenter_id.costs_hour")
    def _compute_x_sbk_costs(self):
        for wo in self:
            hourly = wo.workcenter_id.costs_hour or 0.0
            wo.x_sbk_estimated_cost = (
                (wo.x_sbk_kitchen_expected_min or 0.0) / 60.0 * hourly
            )
            wo.x_sbk_actual_cost = (
                (wo.duration or 0.0) / 60.0 * hourly
            )
            wo.x_sbk_cost_variance = (
                wo.x_sbk_actual_cost - wo.x_sbk_estimated_cost
            )

    @api.depends("production_id")
    def _compute_x_sbk_rework_metrics(self):
        Check = self.env["southbrook.mi.check"]
        for wo in self:
            checks = Check.search([
                ("x_sbk_rework_workorder_id", "=", wo.id),
            ])
            wo.x_sbk_rework_count = len(checks)
            # Cost is read off the rework WOs themselves — i.e. the
            # work orders that the checks point AT — not the inspection
            # cost. We're attributing the spend on the redo back to
            # the original WO that produced the defect.
            hourly = wo.workcenter_id.costs_hour or 0.0
            rework_duration = sum(checks.mapped(
                lambda c: (c.x_sbk_rework_workorder_id.duration or 0.0)
                if c.x_sbk_rework_workorder_id else 0.0
            ))
            wo.x_sbk_rework_cost = rework_duration / 60.0 * hourly

    @api.depends("workcenter_id")
    def _compute_x_sbk_downtime(self):
        Downtime = self.env["southbrook.kitchen.workcenter.downtime"]
        for wo in self:
            rows = Downtime.search([
                ("workorder_id", "=", wo.id),
                ("state", "in", ("active", "closed")),
            ])
            wo.x_sbk_downtime_min = sum(rows.mapped("duration_min"))
            wo.x_sbk_downtime_cost = sum(rows.mapped("downtime_cost"))

    # ------------------------------------------------------------------
    # Convenience — the operation-template duration helper, called via
    # an inherited button in M4.
    # ------------------------------------------------------------------

    def action_sbk_recalc_kitchen_duration(self):
        """Recompute x_sbk_kitchen_expected_min from the operation
        template bound to this WO's BoM operation. No-op when no
        template is bound — Odoo's native duration_expected still
        carries an estimate, the planner can fall back to that.
        """
        for wo in self:
            template = wo._sbk_kitchen_operation_template()
            if not template:
                continue
            driver = wo._sbk_kitchen_driver_value(template)
            complexity = (
                wo.production_id.x_sbk_complexity_factor or 1.0
                if wo.production_id else 1.0
            )
            wo.x_sbk_kitchen_expected_min = template.compute_expected_duration(
                driver_value=driver,
                complexity_factor=complexity,
            )
        return True

    def _sbk_kitchen_operation_template(self):
        """Resolve the operation template bound to this WO's BoM
        operation. Returns False when nothing is bound."""
        self.ensure_one()
        op = self.operation_id
        return op.x_sbk_operation_template_id if op else False

    def _sbk_kitchen_driver_value(self, template):
        """Pull the quantity driver for the template. Honours an
        explicit override on the routing operation, otherwise reads
        product_qty for per-unit templates and 0 for fixed-mode."""
        self.ensure_one()
        override = (
            self.operation_id.x_sbk_driver_override
            if self.operation_id else 0.0
        )
        if override:
            return override
        if template.quantity_driver_type == "fixed":
            return 0.0
        return self.production_id.product_qty or 0.0
