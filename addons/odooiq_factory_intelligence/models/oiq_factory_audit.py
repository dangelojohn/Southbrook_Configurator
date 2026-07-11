# SPDX-License-Identifier: LGPL-3.0-only
"""Factory Intelligence Audit — the read-only data-health / readiness record.

The audit model is a pure persistence + orchestration surface: it holds the two
headline sub-scores and the derived Readiness Level, plus the line-item findings.
All signal *computation* lives in ``oiq.scheduling.intelligence`` (the service
seam) — the audit model never queries mrp.* itself.

Design note on ``readiness_level``: the spec sketches it both as an ``@api.depends``
compute (§4.1) and as an imperative value written by the engine (§5.5). Those
conflict — a stored compute cannot be written by ``analyze()``. We resolve it the
same way §4.1 already resolves ``structural_score``: the engine sets it
imperatively (the authoritative min-gate logic lives in the service, §5.4). The
field is therefore a plain, readonly Integer with a range constraint.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Severity ordering is not alphabetical; map to a rank for _order and top-fix sorting.
SEVERITY_RANK = {"blocker": 30, "warn": 20, "info": 10}
IMPROVEMENT_RANK = {"high": 30, "med": 20, "low": 10}


class OiqFactoryAudit(models.Model):
    _name = "oiq.factory.audit"
    _description = "Factory Intelligence Audit"
    _order = "date desc, id desc"

    date = fields.Datetime(
        required=True, index=True, default=fields.Datetime.now,
        help="When this audit was run.")
    company_id = fields.Many2one(
        "res.company", required=True, index=True,
        default=lambda self: self.env.company)
    readiness_level = fields.Integer(
        readonly=True,
        help="1 Blind · 2 Structured · 3 Observed · 4 Calibrated · 5 Predictive. "
             "Set by the scoring engine as the min of the structural and "
             "behavioral gates.")
    structural_score = fields.Float(
        digits=(5, 2), readonly=True,
        help="0-100. Synchronous data-health score over current MRP config.")
    behavioral_score = fields.Float(
        digits=(5, 2), readonly=True,
        help="0-100. Requires accrued history; unset (see "
             "behavioral_score_available) until enough samples exist.")
    behavioral_score_available = fields.Boolean(
        default=False,
        help="False renders as 'locked, unlocking in N days' rather than a "
             "misleading zero behavioral score.")
    horizon_days = fields.Integer(
        required=True, default=14,
        help="Forward window the horizon-sensitive structural checks used.")
    state = fields.Selection(
        [("draft", "Draft"), ("complete", "Complete")],
        required=True, default="draft")
    summary_text = fields.Text(
        help="Readiness Level + top fixes narrative (never a bare score).")
    finding_ids = fields.One2many(
        "oiq.factory.audit.finding", "audit_id")

    @api.constrains("readiness_level")
    def _check_readiness_level_range(self):
        for audit in self:
            # 0 is allowed only in draft (not yet scored).
            if audit.state == "complete" and not (1 <= audit.readiness_level <= 5):
                raise ValidationError(
                    "Readiness level must be between 1 and 5 on a complete audit.")

    @api.constrains("structural_score", "behavioral_score")
    def _check_score_range(self):
        for audit in self:
            for score in (audit.structural_score, audit.behavioral_score):
                if score and not (0 <= score <= 100):
                    raise ValidationError("Scores must be within [0, 100].")


class OiqFactoryAuditFinding(models.Model):
    _name = "oiq.factory.audit.finding"
    _description = "Factory Intelligence Audit Finding"
    _order = "severity_sequence desc, improvement_sequence desc, id"

    audit_id = fields.Many2one(
        "oiq.factory.audit", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(
        related="audit_id.company_id", store=True, index=True, readonly=True)
    signal_code = fields.Char(
        required=True, index=True,
        help="One of the fixed S1-S7 (structural) / B1-B4 (behavioral) codes.")
    tier = fields.Selection(
        [("structural", "Structural"), ("behavioral", "Behavioral")],
        required=True)
    severity = fields.Selection(
        [("info", "Info"), ("warn", "Warn"), ("blocker", "Blocker")],
        required=True, default="warn", index=True)
    severity_sequence = fields.Integer(
        compute="_compute_ranks", store=True)
    improvement_sequence = fields.Integer(
        compute="_compute_ranks", store=True)
    title = fields.Char(required=True)
    detail = fields.Text()
    affected_count = fields.Integer(default=0)
    recommended_action = fields.Text(
        help="The concrete next step — the acquisition-hook framing.")
    expected_improvement = fields.Selection(
        [("low", "Low"), ("med", "Medium"), ("high", "High")],
        required=True, default="med")

    @api.depends("severity", "expected_improvement")
    def _compute_ranks(self):
        for f in self:
            f.severity_sequence = SEVERITY_RANK.get(f.severity, 0)
            f.improvement_sequence = IMPROVEMENT_RANK.get(f.expected_improvement, 0)
