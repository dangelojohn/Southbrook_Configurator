# SPDX-License-Identifier: LGPL-3.0-only
"""Shadow scheduling models — a read-only re-plan compared against Odoo's own
plan and (later) actuals.

Strict invariant: these models only ever store the engine's *proposal*. Nothing
here — and nothing in the service that fills them — writes to mrp.production /
mrp.workorder / mrp.workcenter.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class OiqScheduleRun(models.Model):
    _name = "oiq.schedule.run"
    _description = "OdooIQ Shadow Schedule Run"
    _order = "date desc, id desc"

    date = fields.Datetime(required=True, index=True, default=fields.Datetime.now)
    company_id = fields.Many2one(
        "res.company", required=True, index=True,
        default=lambda self: self.env.company)
    horizon_days = fields.Integer(required=True, default=14)
    algorithm = fields.Selection(
        [("edd_greedy", "EDD Greedy")], required=True, default="edd_greedy")
    state = fields.Selection(
        [("draft", "Draft"), ("computing", "Computing"),
         ("complete", "Complete"), ("failed", "Failed")],
        required=True, default="draft", index=True)
    makespan_min = fields.Float(digits=(10, 1))
    predicted_late_count = fields.Integer(default=0)
    notes = fields.Text()
    slot_ids = fields.One2many("oiq.schedule.slot", "run_id")

    @api.constrains("horizon_days")
    def _check_horizon_positive(self):
        for run in self:
            if run.horizon_days <= 0:
                raise ValidationError("Horizon must be a positive number of days.")


class OiqScheduleSlot(models.Model):
    _name = "oiq.schedule.slot"
    _description = "OdooIQ Shadow Schedule Slot"
    _order = "run_id, seq, planned_start"

    run_id = fields.Many2one(
        "oiq.schedule.run", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(
        related="run_id.company_id", store=True, index=True, readonly=True)
    production_id = fields.Many2one("mrp.production", required=True, index=True)
    workorder_id = fields.Many2one("mrp.workorder", required=True, index=True)
    workcenter_id = fields.Many2one("mrp.workcenter", required=True, index=True)
    seq = fields.Integer(required=True, default=10)
    planned_start = fields.Datetime(required=True)
    planned_finish = fields.Datetime(required=True)
    predicted_complete = fields.Datetime(required=True)
    late_risk = fields.Float(digits=(5, 2))
    vs_odoo_delta_min = fields.Float(
        digits=(10, 1),
        help="OdooIQ planned_finish minus Odoo's own planned finish, in minutes. "
             "Positive = shadow predicts later than Odoo.")
    vs_actual_delta_min = fields.Float(
        digits=(10, 1),
        help="Backfilled on WO completion: actual finish minus predicted "
             "completion, in minutes. Unset while the WO is open.")

    @api.constrains("planned_start", "planned_finish")
    def _check_planned_order(self):
        for slot in self:
            if slot.planned_finish < slot.planned_start:
                raise ValidationError("Planned finish cannot precede planned start.")

    @api.constrains("late_risk")
    def _check_late_risk_range(self):
        for slot in self:
            if slot.late_risk and not (0 <= slot.late_risk <= 100):
                raise ValidationError("Late risk must be within [0, 100].")
