# SPDX-License-Identifier: LGPL-3.0-only
"""Per-job phase log — one row per (job × phase).

This is the line-level granularity the installer interacts with on
site: start a phase, attach photos, mark done. Photo-gated completion
is enforced server-side in ``action_mark_done``.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


STATES = [
    ("pending", "Pending"),
    ("in_progress", "In Progress"),
    ("done", "Done"),
    ("skipped", "Skipped"),
]


class SouthbrookInstallerStageLog(models.Model):
    _name = "southbrook.installer.stage.log"
    _description = "Installer Job — Phase Log"
    _order = "job_id, sequence, id"
    _rec_name = "display_name"

    job_id = fields.Many2one(
        "southbrook.installer.job",
        required=True,
        ondelete="cascade",
        index=True,
    )
    phase_id = fields.Many2one(
        "southbrook.installer.phase",
        required=True,
        ondelete="restrict",
        index=True,
    )
    # Stored related so list/search by sequence stays cheap.
    sequence = fields.Integer(
        related="phase_id.sequence",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        STATES,
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    start_time = fields.Datetime(readonly=True, copy=False)
    complete_time = fields.Datetime(readonly=True, copy=False)
    duration_mins = fields.Float(
        compute="_compute_duration_mins",
        store=True,
        digits=(8, 2),
        help="Actual phase duration: complete_time minus start_time.",
    )
    estimated_duration_mins = fields.Integer(
        related="phase_id.estimated_duration_mins",
        store=False,
        readonly=True,
    )
    photo_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_installer_stage_log_attachment_rel",
        "log_id",
        "attachment_id",
        string="Phase Photos",
    )
    photo_count = fields.Integer(
        compute="_compute_photo_count",
        store=True,
    )
    min_photos_required = fields.Integer(
        related="phase_id.min_photos",
        store=False,
        readonly=True,
    )
    photo_gate_passed = fields.Boolean(
        compute="_compute_photo_gate_passed",
        store=True,
        help="True when photo_count meets the phase's minimum (or the "
             "phase doesn't require photos).",
    )
    notes = fields.Text()
    completed_by_id = fields.Many2one(
        "hr.employee",
        readonly=True,
        copy=False,
    )
    gps_lat = fields.Float(digits=(10, 7), readonly=True, copy=False)
    gps_lng = fields.Float(digits=(10, 7), readonly=True, copy=False)

    _job_phase_uniq = models.Constraint(
        "unique(job_id, phase_id)",
        "Each phase can only be logged once per installer job.",
    )

    # Re-declared so the compute override binds in v19.
    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
        recursive=False,
    )

    @api.depends("phase_id.name", "phase_id.code", "job_id.name")
    def _compute_display_name(self):
        for rec in self:
            phase_label = rec.phase_id.code or rec.phase_id.name or "?"
            job_label = rec.job_id.name or _("New Job")
            rec.display_name = f"{job_label} / {phase_label}"

    @api.depends("photo_ids")
    def _compute_photo_count(self):
        for rec in self:
            rec.photo_count = len(rec.photo_ids)

    # Depend on the M2M directly (the trigger), not on the intermediate
    # stored compute `photo_count` — keeps the recompute graph one-hop
    # and avoids fragile ordering under m2m write storms.
    @api.depends("photo_ids", "phase_id.require_photo", "phase_id.min_photos")
    def _compute_photo_gate_passed(self):
        for rec in self:
            if not rec.phase_id.require_photo:
                rec.photo_gate_passed = True
            else:
                rec.photo_gate_passed = len(rec.photo_ids) >= (
                    rec.phase_id.min_photos or 0
                )

    @api.depends("start_time", "complete_time")
    def _compute_duration_mins(self):
        for rec in self:
            if rec.start_time and rec.complete_time:
                delta = rec.complete_time - rec.start_time
                rec.duration_mins = delta.total_seconds() / 60.0
            else:
                rec.duration_mins = 0.0

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_mark_in_progress(self):
        """Operator taps Start. Records start_time once."""
        for rec in self:
            if rec.state == "done":
                raise ValidationError(_(
                    "Phase %(p)s is already done — cannot restart.",
                ) % {"p": rec.phase_id.display_name})
            vals = {"state": "in_progress"}
            if not rec.start_time:
                vals["start_time"] = fields.Datetime.now()
            rec.write(vals)

    def action_mark_done(self):
        """Operator taps Complete. Enforces photo gate."""
        for rec in self:
            if rec.state == "done":
                continue
            if rec.phase_id.require_photo and not rec.photo_gate_passed:
                raise ValidationError(_(
                    "Cannot mark phase '%(p)s' done — needs at least "
                    "%(n)s photo(s); %(c)s attached.",
                ) % {
                    "p": rec.phase_id.display_name,
                    "n": rec.phase_id.min_photos,
                    "c": rec.photo_count,
                })
            employee = self.env.user.employee_id
            rec.write({
                "state": "done",
                "complete_time": fields.Datetime.now(),
                "completed_by_id": employee.id if employee else False,
            })
            rec.job_id.message_post(body=_(
                "✅ Phase <b>%(p)s</b> completed by %(u)s "
                "(%(d).1f min, %(n)s photo(s)).",
            ) % {
                "p": rec.phase_id.display_name,
                "u": self.env.user.display_name,
                "d": rec.duration_mins,
                "n": rec.photo_count,
            })

    def action_mark_skipped(self):
        """Skip a phase that doesn't apply on this job (e.g. lighting)."""
        for rec in self:
            if rec.state == "done":
                raise ValidationError(_(
                    "Phase %(p)s is already done — cannot skip.",
                ) % {"p": rec.phase_id.display_name})
            rec.write({
                "state": "skipped",
                "complete_time": fields.Datetime.now(),
            })
            rec.job_id.message_post(body=_(
                "⏭ Phase <b>%(p)s</b> skipped by %(u)s.",
            ) % {
                "p": rec.phase_id.display_name,
                "u": self.env.user.display_name,
            })
