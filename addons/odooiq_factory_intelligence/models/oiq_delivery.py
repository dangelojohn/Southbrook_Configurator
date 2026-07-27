# SPDX-License-Identifier: LGPL-3.0-only
"""Delivery confidence — a defensible completion RANGE per manufacturing order.

Never a bare percentage, never a single date: always completion_start →
completion_end, a quality label, and an honest accuracy claim backed by the
factory's own past predictions.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class OiqDeliveryEstimate(models.Model):
    _name = "oiq.delivery.estimate"
    _description = "OdooIQ Delivery Estimate"
    _order = "production_id"

    production_id = fields.Many2one("mrp.production", required=True, index=True)
    company_id = fields.Many2one(
        related="production_id.company_id", store=True, index=True, readonly=True)
    completion_start = fields.Datetime(required=True)
    completion_end = fields.Datetime(required=True)
    prediction_quality = fields.Selection(
        [("low", "Low"), ("med", "Medium"), ("high", "High")],
        required=True, default="low")
    historical_accuracy_pct = fields.Float(
        digits=(5, 2),
        help="% of past estimates in this cohort whose actual finish landed "
             "within accuracy_window_days of the promised midpoint. Null until "
             "enough completed history exists.")
    accuracy_window_days = fields.Integer(default=3)
    sample_count = fields.Integer(default=0)
    basis_text = fields.Text(
        help="Plain-language explanation: cohort, sample size, quality, and why "
             "the range has the width it has. Never ship a range without it.")

    _production_unique = models.Constraint(
        "UNIQUE(production_id)",
        "One live delivery estimate per manufacturing order.")

    @api.constrains("completion_start", "completion_end")
    def _check_range_order(self):
        for est in self:
            if est.completion_end < est.completion_start:
                raise ValidationError("Completion end cannot precede start.")

    @api.constrains("historical_accuracy_pct")
    def _check_accuracy_range(self):
        for est in self:
            if est.historical_accuracy_pct and not (0 <= est.historical_accuracy_pct <= 100):
                raise ValidationError("Historical accuracy must be within [0, 100].")
