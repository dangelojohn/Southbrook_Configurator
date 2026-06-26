# SPDX-License-Identifier: LGPL-3.0-only
"""Installer Job — the central record for one on-site installation visit.

State machine (the 8-stage workflow in
``data/southbrook_installer_stage_data.xml``):

    SCHEDULED → PRE_SITE_CONFIRM → DELIVERY_RECEIVED →
    INSTALLATION_IN_PROGRESS → FINAL_SIGN_OFF →
    CLOSED_OUT → COMPLETE → INVOICED

Gate philosophy: ``action_advance_stage`` collects ALL failing exit
gates on the current stage and surfaces them in a single
``UserError``. The installer never has to submit ten times to find
ten different problems.

Placeholders flagged in this build (replaced in later phases):

- ``delivery_confirmed`` — flipped manually here; computed from the
  delivery manifest in Phase 1.2.
- ``sign_request_ref`` — Char placeholder; replaced with a
  Many2one → sign.request in Phase 2.3.
- ``closeout_done`` — flipped manually here; computed from the
  close-out checklist in Phase 1.3.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


PRIORITY = [
    ("0", "Normal"),
    ("1", "Urgent"),
]


RATING = [
    ("1", "★ — Poor"),
    ("2", "★★ — Below"),
    ("3", "★★★ — Average"),
    ("4", "★★★★ — Good"),
    ("5", "★★★★★ — Excellent"),
]


class SouthbrookInstallerJob(models.Model):
    _name = "southbrook.installer.job"
    _description = "Southbrook Installer Job"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "scheduled_date desc, id desc"
    _rec_name = "name"

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(
        default=lambda self: _("New"),
        required=True,
        copy=False,
        readonly=True,
        index=True,
        tracking=True,
        help="Job reference, auto-allocated INST-<year>-<5-digit-seq>.",
    )
    active = fields.Boolean(default=True)
    priority = fields.Selection(
        PRIORITY,
        default="0",
        tracking=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Site / project / contact
    # ------------------------------------------------------------------
    project_id = fields.Many2one(
        "project.project",
        string="Builder Project",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
    )
    unit_number = fields.Char(
        string="Suite / Unit #",
        required=True,
        tracking=True,
    )
    site_address = fields.Char(
        required=True,
        tracking=True,
    )
    site_address_lat = fields.Float(
        string="Site GPS Latitude",
        digits=(10, 7),
    )
    site_address_lng = fields.Float(
        string="Site GPS Longitude",
        digits=(10, 7),
    )
    builder_contact_id = fields.Many2one(
        "res.partner",
        string="Builder Site Supervisor",
        ondelete="set null",
    )
    builder_phone = fields.Char(
        related="builder_contact_id.phone",
        readonly=True,
        store=False,
    )

    # ------------------------------------------------------------------
    # Crew + schedule
    # ------------------------------------------------------------------
    lead_installer_id = fields.Many2one(
        "hr.employee",
        string="Lead Installer",
        required=True,
        index=True,
        tracking=True,
    )
    assigned_crew_ids = fields.Many2many(
        "hr.employee",
        "southbrook_installer_job_crew_rel",
        "job_id",
        "employee_id",
        string="Installation Crew",
    )
    scheduled_date = fields.Datetime(
        string="Installation Date / Time",
        required=True,
        tracking=True,
        index=True,
    )
    arrival_window_end = fields.Datetime(string="Latest Arrival Time")
    estimated_duration_hours = fields.Float(
        string="Est. Duration (hrs)",
        default=8.0,
    )

    # ------------------------------------------------------------------
    # Stage workflow
    # ------------------------------------------------------------------
    stage_id = fields.Many2one(
        "southbrook.installer.stage",
        string="Current Stage",
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self._default_stage_id(),
        group_expand="_read_group_stage_ids",
    )
    stage_log_ids = fields.One2many(
        "southbrook.installer.stage.log",
        "job_id",
        string="Phase Log",
    )
    completion_pct = fields.Float(
        compute="_compute_completion_pct",
        store=True,
        digits=(5, 2),
        tracking=True,
        help="(done phases / active phases) × 100. Skipped phases "
             "count as not-counting-toward-total.",
    )

    # ------------------------------------------------------------------
    # Delivery + GPS + telemetry
    # ------------------------------------------------------------------
    kit_picking_id = fields.Many2one(
        "stock.picking",
        string="Kit Delivery Order",
        ondelete="set null",
    )
    delivery_confirmed = fields.Boolean(
        default=False,
        tracking=True,
        help="Placeholder field — manually flipped in Phase 1.1. Will "
             "be computed from southbrook.delivery.manifest in Phase 1.2.",
    )
    gps_arrival_time = fields.Datetime(readonly=True, copy=False)
    gps_arrival_lat = fields.Float(digits=(10, 7), readonly=True, copy=False)
    gps_arrival_lng = fields.Float(digits=(10, 7), readonly=True, copy=False)
    gps_departure_time = fields.Datetime(readonly=True, copy=False)
    gps_departure_lat = fields.Float(digits=(10, 7), readonly=True, copy=False)
    gps_departure_lng = fields.Float(digits=(10, 7), readonly=True, copy=False)
    on_site_duration_hrs = fields.Float(
        compute="_compute_on_site_duration",
        store=True,
        digits=(6, 2),
    )

    # ------------------------------------------------------------------
    # Blocking + safety
    # ------------------------------------------------------------------
    is_blocked = fields.Boolean(
        default=False,
        tracking=True,
        index=True,
        help="Placeholder — manually flipped here. Phase 1.2 wires this "
             "to live damage flags on the job.",
    )

    # ------------------------------------------------------------------
    # Sign-off / close-out placeholders
    # ------------------------------------------------------------------
    sign_request_ref = fields.Char(
        string="Sign Request Reference",
        copy=False,
        help="Placeholder Char — Phase 2.3 replaces with Many2one to "
             "sign.request when the sign module is added to the stack.",
    )
    sign_off_received = fields.Boolean(
        default=False,
        copy=False,
        tracking=True,
        help="Set True when the builder has signed off. Used by the "
             "FINAL_SIGN_OFF exit gate.",
    )
    closeout_done = fields.Boolean(
        default=False,
        copy=False,
        tracking=True,
        help="Placeholder — flipped manually here. Phase 1.3 wires this "
             "to a southbrook.installer.closeout record.",
    )

    # ------------------------------------------------------------------
    # Feedback + content
    # ------------------------------------------------------------------
    phase_photo_ids = fields.Many2many(
        "ir.attachment",
        "southbrook_installer_job_photo_rel",
        "job_id",
        "attachment_id",
        string="Job Photo Gallery",
    )
    builder_rating = fields.Selection(RATING, tracking=True)
    builder_rating_notes = fields.Text()
    notes = fields.Html()

    # ------------------------------------------------------------------
    # Kanban + UX
    # ------------------------------------------------------------------
    color = fields.Integer(
        compute="_compute_color",
        store=True,
        help="Kanban color: green=on track, red=blocked, grey=terminal. "
             "Yellow (open non-blocking issues) is wired in Phase 1.2 "
             "when damage flags exist.",
    )
    stage_is_terminal = fields.Boolean(
        related="stage_id.is_terminal",
        store=True,
        readonly=True,
    )

    # Smart-button counters
    stage_log_count = fields.Integer(
        compute="_compute_stage_log_count",
        store=False,
    )
    stage_log_done_count = fields.Integer(
        compute="_compute_stage_log_count",
        store=False,
    )

    # ==================================================================
    # Defaults / model helpers
    # ==================================================================
    @api.model
    def _default_stage_id(self):
        """The lowest-sequence stage — typically SCHEDULED."""
        return self.env["southbrook.installer.stage"].search(
            [], order="sequence asc, id asc", limit=1,
        ).id or False

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Show ALL stages in kanban grouping, even empty ones."""
        return self.env["southbrook.installer.stage"].search(
            [], order="sequence",
        )

    # ==================================================================
    # Compute
    # ==================================================================
    @api.depends("stage_log_ids.state")
    def _compute_completion_pct(self):
        for rec in self:
            logs = rec.stage_log_ids
            # Skipped phases drop out of both numerator and denominator.
            considered = logs.filtered(lambda l: l.state != "skipped")
            done = considered.filtered(lambda l: l.state == "done")
            total = len(considered)
            rec.completion_pct = (100.0 * len(done) / total) if total else 0.0

    @api.depends("gps_arrival_time", "gps_departure_time")
    def _compute_on_site_duration(self):
        for rec in self:
            if rec.gps_arrival_time and rec.gps_departure_time:
                delta = rec.gps_departure_time - rec.gps_arrival_time
                rec.on_site_duration_hrs = delta.total_seconds() / 3600.0
            else:
                rec.on_site_duration_hrs = 0.0

    @api.depends("is_blocked", "stage_is_terminal", "stage_id.sequence")
    def _compute_color(self):
        for rec in self:
            if rec.is_blocked:
                rec.color = 9  # red
            elif rec.stage_is_terminal:
                rec.color = 11  # grey
            else:
                rec.color = 10  # green

    @api.depends("stage_log_ids", "stage_log_ids.state")
    def _compute_stage_log_count(self):
        for rec in self:
            rec.stage_log_count = len(rec.stage_log_ids)
            rec.stage_log_done_count = len(
                rec.stage_log_ids.filtered(lambda l: l.state == "done")
            )

    # ==================================================================
    # CRUD
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Allocate sequence + spawn one phase log per active phase."""
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "southbrook.installer.job"
                ) or _("INST/New")
        jobs = super().create(vals_list)
        for job in jobs:
            job._spawn_phase_logs()
        return jobs

    def _spawn_phase_logs(self):
        """Idempotent: creates one stage_log per active phase that is
        not already linked. Safe to call again after adding a new phase."""
        Log = self.env["southbrook.installer.stage.log"]
        Phase = self.env["southbrook.installer.phase"]
        for job in self:
            existing = job.stage_log_ids.mapped("phase_id")
            missing = Phase.search([("active", "=", True)]) - existing
            if missing:
                Log.create([
                    {"job_id": job.id, "phase_id": phase.id}
                    for phase in missing.sorted("sequence")
                ])

    # ==================================================================
    # Stage advance — the heart of the workflow
    # ==================================================================
    def action_advance_stage(self):
        """Advance to the next stage, validating ALL exit gates on the
        current stage in one pass. Surfaces all failures together so
        the installer fixes them all before resubmitting.

        Raises UserError listing every missing gate when not ready.
        """
        for job in self:
            current = job.stage_id
            if not current:
                raise UserError(_("Job has no current stage."))
            failures = job._collect_gate_failures(current)
            if failures:
                msg = _("Cannot advance from '%(s)s'. Missing:") % {
                    "s": current.name,
                }
                lines = "\n".join(f"  • {f}" for f in failures)
                raise UserError(f"{msg}\n{lines}")

            target = current.get_next_stage()
            if not target:
                raise UserError(_(
                    "'%(s)s' is the final stage — nothing to advance to.",
                ) % {"s": current.name})

            job.write({"stage_id": target.id})
            job.message_post(body=_(
                "↪ Stage advanced: <b>%(f)s</b> → <b>%(t)s</b> by %(u)s.",
            ) % {
                "f": current.name,
                "t": target.name,
                "u": self.env.user.display_name,
            })

    def _collect_gate_failures(self, stage):
        """Return a list of human-readable strings, one per failing
        exit gate on ``stage``. Empty list = all gates passed."""
        self.ensure_one()
        failures = []
        if stage.gate_require_delivery_confirmed and not self.delivery_confirmed:
            failures.append(_("Delivery manifest is not confirmed."))
        if stage.gate_require_all_phases_done:
            considered = self.stage_log_ids.filtered(
                lambda l: l.state != "skipped"
            )
            open_logs = considered.filtered(lambda l: l.state != "done")
            if open_logs:
                names = ", ".join(
                    log.phase_id.code or log.phase_id.name
                    for log in open_logs.sorted("sequence")[:5]
                )
                more = ""
                if len(open_logs) > 5:
                    more = _(" (+%d more)") % (len(open_logs) - 5)
                failures.append(_(
                    "Installation phases not done: %(names)s%(more)s.",
                ) % {"names": names, "more": more})
        if stage.gate_require_sign_off and not self.sign_off_received:
            failures.append(_("Builder sign-off has not been recorded."))
        if stage.gate_require_closeout_done and not self.closeout_done:
            failures.append(_("Close-out checklist has not been submitted."))
        return failures

    # ==================================================================
    # On-site button actions
    # ==================================================================
    def action_mark_arrived(self):
        """Crew arrives on site — records arrival timestamp and copies
        the planned site coordinates into the arrival_lat/lng fields
        as a default. The real device GPS is supplied by the mobile
        client (Phase 3 REST API will overwrite these via the
        ``/jobs/<id>/arrive`` endpoint body).

        Also auto-advances out of SCHEDULED if that stage's gates pass.
        """
        for job in self:
            if job.gps_arrival_time:
                raise UserError(_(
                    "Arrival already recorded at %s.",
                ) % fields.Datetime.to_string(job.gps_arrival_time))
            job.write({
                "gps_arrival_time": fields.Datetime.now(),
                # Default to planned site coords until the mobile client
                # overwrites with real device GPS. See docstring.
                "gps_arrival_lat": job.site_address_lat,
                "gps_arrival_lng": job.site_address_lng,
            })
            job.message_post(body=_(
                "📍 Arrived on site at %(t)s (recorded by %(u)s).",
            ) % {
                "t": fields.Datetime.to_string(job.gps_arrival_time),
                "u": self.env.user.display_name,
            })
            # If we're at the start stage, auto-advance through it.
            if job.stage_id and not job._collect_gate_failures(job.stage_id):
                if job.stage_id.code == "SCHEDULED":
                    job.action_advance_stage()

    def action_mark_departed(self):
        for job in self:
            if job.gps_departure_time:
                raise UserError(_("Departure already recorded."))
            if not job.gps_arrival_time:
                raise UserError(_(
                    "Cannot record departure before arrival.",
                ))
            now = fields.Datetime.now()
            job.write({"gps_departure_time": now})
            # Compute duration inline — the stored compute
            # `on_site_duration_hrs` has not flushed yet at this point
            # and would read 0.00 in the chatter line.
            delta_hrs = (now - job.gps_arrival_time).total_seconds() / 3600.0
            job.message_post(body=_(
                "🚚 Departed site at %(t)s — on-site duration %(d).2f hr.",
            ) % {
                "t": fields.Datetime.to_string(now),
                "d": delta_hrs,
            })

    def action_view_phase_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Installation Phases"),
            "res_model": "southbrook.installer.stage.log",
            "view_mode": "list,form",
            "domain": [("job_id", "=", self.id)],
            "context": {"default_job_id": self.id},
        }

    def action_record_signoff(self):
        """Placeholder for Phase 2.3 — flips the manual flag so the
        FINAL_SIGN_OFF → CLOSED_OUT gate can be exercised today."""
        for job in self:
            if job.sign_off_received:
                continue
            job.write({"sign_off_received": True})
            job.message_post(body=_(
                "✍ Builder sign-off recorded (placeholder — Phase 2.3 "
                "wires sign.request)."
            ))

    def action_mark_closeout_done(self):
        """Placeholder for Phase 1.3 — same pattern."""
        for job in self:
            if job.closeout_done:
                continue
            job.write({"closeout_done": True})
            job.message_post(body=_(
                "📋 Close-out checklist submitted (placeholder — Phase "
                "1.3 wires southbrook.installer.closeout)."
            ))
