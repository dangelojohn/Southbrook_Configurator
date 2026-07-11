# SPDX-License-Identifier: LGPL-3.0-only
"""Calibration engine models — the Factory Learning Graph (the moat).

`oiq.completion.observation` is the append-only raw signal (estimated vs actual
per completed work order). `oiq.calibration.factor` is the learned per-tenant
correction rolled up from those observations by scope.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class OiqCompletionObservation(models.Model):
    _name = "oiq.completion.observation"
    _description = "OdooIQ Completion Observation"
    _order = "observed_at desc, id desc"

    workorder_id = fields.Many2one("mrp.workorder", required=True, index=True)
    production_id = fields.Many2one("mrp.production", required=True, index=True)
    company_id = fields.Many2one(
        related="production_id.company_id", store=True, index=True, readonly=True)
    product_id = fields.Many2one("product.product", required=True, index=True)
    product_family = fields.Char(index=True)
    operation_category = fields.Char(index=True)
    workcenter_id = fields.Many2one("mrp.workcenter", required=True, index=True)
    estimated_min = fields.Float(digits=(10, 1), required=True)
    actual_min = fields.Float(digits=(10, 1), required=True)
    ratio = fields.Float(digits=(6, 3), compute="_compute_ratio", store=True)
    context_json = fields.Text()
    delay_reason = fields.Char()
    observed_at = fields.Datetime(
        required=True, index=True, default=fields.Datetime.now)

    _workorder_unique = models.Constraint(
        "UNIQUE(workorder_id)",
        "Only one completion observation per work order.")

    @api.depends("estimated_min", "actual_min")
    def _compute_ratio(self):
        for obs in self:
            obs.ratio = (obs.actual_min / obs.estimated_min
                         if obs.estimated_min > 0 else 0.0)

    @api.constrains("estimated_min", "actual_min")
    def _check_non_negative(self):
        for obs in self:
            if obs.estimated_min < 0 or obs.actual_min < 0:
                raise ValidationError("Observation minutes must be non-negative.")


class OiqCalibrationFactor(models.Model):
    _name = "oiq.calibration.factor"
    _description = "OdooIQ Calibration Factor"
    _order = "scope, key"

    # company_id added beyond the spec §4.7 so the learning graph is per-tenant
    # (the moat, §7.8) — factors must never leak across companies.
    company_id = fields.Many2one(
        "res.company", required=True, index=True,
        default=lambda self: self.env.company)
    scope = fields.Selection(
        [("operation_category", "Operation Category"),
         ("product_family", "Product Family"),
         ("workcenter", "Work Center"),
         ("composite", "Composite")],
        required=True, index=True)
    key = fields.Char(required=True, index=True)
    multiplier = fields.Float(digits=(6, 3), required=True, default=1.0)
    sample_count = fields.Integer(required=True, default=0)
    confidence = fields.Float(digits=(4, 3), required=True, default=0.0)
    last_recomputed = fields.Datetime(
        required=True, default=fields.Datetime.now)

    _scope_key_unique = models.Constraint(
        "UNIQUE(company_id, scope, key)",
        "One calibration factor per company/scope/key.")

    @api.constrains("confidence")
    def _check_confidence_range(self):
        for f in self:
            if not (0 <= f.confidence <= 1):
                raise ValidationError("Confidence must be within [0, 1].")

    @api.constrains("multiplier")
    def _check_multiplier_positive(self):
        for f in self:
            if f.multiplier <= 0:
                raise ValidationError("Multiplier must be positive.")
