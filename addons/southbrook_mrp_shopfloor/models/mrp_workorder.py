# SPDX-License-Identifier: LGPL-3.0-only
"""Work-order scheduling dates, sequencing and capacity-load rebuild.

Deliberately writes ``date_planned_start_wo`` / ``date_planned_finished_wo``
and never native ``date_start`` / ``date_finished``. The vendor module made
the same choice for a good reason: writing the native fields makes Odoo
create resource calendar leaves, which then double-book the workcenter
against the very schedule being written.
"""

from odoo import api, fields, models


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    date_planned_start_wo = fields.Datetime(
        "Scheduled Start", copy=False, index=True,
        help="Shop-floor planned start. Separate from the native scheduling "
             "fields so that planning does not generate calendar leaves.")
    date_planned_finished_wo = fields.Datetime("Scheduled Finish", copy=False)
    date_actual_start_wo = fields.Datetime(
        "Actual Start", compute="_compute_actual_dates", store=True)
    date_actual_finished_wo = fields.Datetime(
        "Actual Finish", compute="_compute_actual_dates", store=True)
    sfc_sequence = fields.Integer(
        "Shop Sequence", compute="_compute_sfc_sequence", store=True,
        readonly=False,
        help="Execution order within the manufacturing order. Defaults to "
             "the routing operation sequence and may be overridden.")
    qty_output_wo = fields.Float(
        "Output Quantity", compute="_compute_qty_output_wo", store=True,
        digits="Product Unit of Measure")
    wo_capacity_requirements = fields.Float(
        "Required Capacity (hours)", compute="_compute_capacity_requirements",
        store=True)

    @api.depends("operation_id.sequence")
    def _compute_sfc_sequence(self):
        for wo in self:
            if not wo.sfc_sequence:
                wo.sfc_sequence = wo.operation_id.sequence or 10

    @api.depends("time_ids.date_start", "time_ids.date_end", "state")
    def _compute_actual_dates(self):
        for wo in self:
            starts = wo.time_ids.filtered("date_start").mapped("date_start")
            ends = wo.time_ids.filtered("date_end").mapped("date_end")
            wo.date_actual_start_wo = min(starts) if starts else False
            # Only a finished work order has a meaningful actual finish; an
            # in-flight one has an end date on its last closed time log,
            # which is not the same thing.
            wo.date_actual_finished_wo = (
                max(ends) if ends and wo.state in ("done", "cancel") else False)

    @api.depends("qty_produced", "qty_production", "state")
    def _compute_qty_output_wo(self):
        for wo in self:
            wo.qty_output_wo = (
                wo.qty_produced if wo.state == "done" else wo.qty_production)

    @api.depends("duration_expected")
    def _compute_capacity_requirements(self):
        for wo in self:
            wo.wo_capacity_requirements = (wo.duration_expected or 0.0) / 60.0

    # ------------------------------------------------------------------
    # Calendar walking
    # ------------------------------------------------------------------
    def _sfc_plan_from(self, start):
        """Place this work order starting at or after *start*.

        Walks the workcenter calendar so a job never lands in the middle of a
        night or a weekend. Returns the finish datetime.

        This is calendar-aware but NOT contention-aware: it does not consult
        what else is already booked on the workcenter. That limitation is
        inherited from the module this replaces and is called out rather than
        hidden — the finite-capacity engine is the canonical path when
        cross-order contention matters.
        """
        self.ensure_one()
        calendar = self.workcenter_id._sfc_calendar()
        hours = (self.duration_expected or 0.0) / 60.0
        if not hours:
            return start
        if calendar:
            return calendar.plan_hours(hours, start, compute_leaves=True) or start
        return fields.Datetime.add(start, hours=hours)

    def _rebuild_capacity_load(self):
        """Refresh the daily load rows for these work orders.

        Consumed by the scheduling engine after it applies a schedule.
        """
        Load = self.env["mrp.workcenter.load"]
        Load.search([("workorder_id", "in", self.ids)]).unlink()
        vals = []
        for wo in self:
            if not wo.workcenter_id or not wo.date_planned_start_wo:
                continue
            vals.append({
                "workcenter_id": wo.workcenter_id.id,
                "workorder_id": wo.id,
                "date_planned": wo.date_planned_start_wo,
                "wo_capacity_requirements": wo.wo_capacity_requirements,
            })
        if vals:
            Load.create(vals)
        return True
