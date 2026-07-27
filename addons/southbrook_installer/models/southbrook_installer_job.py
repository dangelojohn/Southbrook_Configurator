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
    manifest_ids = fields.One2many(
        "southbrook.delivery.manifest",
        "job_id",
        string="Delivery Manifests",
    )
    manifest_id = fields.Many2one(
        "southbrook.delivery.manifest",
        string="Active Delivery Manifest",
        compute="_compute_active_manifest",
        store=True,
        ondelete="set null",
        help="Most-recent manifest on this job. Drives "
             "delivery_confirmed.",
    )
    delivery_confirmed = fields.Boolean(
        compute="_compute_delivery_confirmed",
        store=True,
        tracking=True,
        help="True when the active delivery manifest is signed off "
             "(state in 'confirmed' or 'discrepancy'). Wired in 1.2.",
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
    damage_flag_ids = fields.One2many(
        "southbrook.damage.flag",
        "job_id",
        string="Damage Flags",
    )
    is_blocked = fields.Boolean(
        compute="_compute_is_blocked",
        store=True,
        tracking=True,
        index=True,
        help="True when any non-resolved damage flag on this job has "
             "urgency='blocking'. Wired in 1.2.",
    )
    open_damage_count = fields.Integer(
        compute="_compute_open_damage_count",
        store=True,
        help="Count of damage flags not in terminal state "
             "(resolved/cancelled).",
    )
    blocking_damage_count = fields.Integer(
        compute="_compute_open_damage_count",
        store=True,
    )

    # ------------------------------------------------------------------
    # Sign-off (CE-safe: canvas signature via punchlist) + closeout
    # ------------------------------------------------------------------
    sign_request_ref = fields.Char(
        string="External Sign Request Ref",
        copy=False,
        help="Optional external signing-service reference (DocuSign / "
             "HelloSign / Adobe Sign). Not used by the in-platform "
             "sign-off path — see punchlist_id.signature_data.",
    )
    punchlist_ids = fields.One2many(
        "southbrook.installer.punchlist",
        "job_id",
        string="Punchlist (1:1)",
    )
    punchlist_id = fields.Many2one(
        "southbrook.installer.punchlist",
        compute="_compute_punchlist_id",
        store=True,
        readonly=True,
        ondelete="set null",
    )
    sign_off_received = fields.Boolean(
        compute="_compute_sign_off_received",
        store=True,
        tracking=True,
        help="True when the punchlist record carries a signature blob "
             "AND printed name AND is in state 'complete'. Used by the "
             "FINAL_SIGN_OFF exit gate.",
    )
    closeout_id = fields.Many2one(
        "southbrook.installer.closeout",
        compute="_compute_closeout_id",
        store=True,
        readonly=True,
        ondelete="set null",
        help="The (unique) close-out record for this job. Computed "
             "from the inverse southbrook.installer.closeout.job_id.",
    )
    closeout_ids = fields.One2many(
        "southbrook.installer.closeout",
        "job_id",
        string="Close-Out (1:1)",
    )
    closeout_done = fields.Boolean(
        compute="_compute_closeout_done",
        store=True,
        tracking=True,
        help="True when the unique close-out record is in state "
             "'complete'. Wired in 1.3.",
    )
    tool_loan_ids = fields.One2many(
        "southbrook.installer.tool.loan",
        "job_id",
        string="Tool Loans",
    )
    # store=True: these are fetched for up to 200 jobs on every dashboard
    # load and 30s poll; storing them (deps already declared) avoids a
    # recompute+refetch each time, matching completion_pct/open_damage_count.
    tool_loan_count = fields.Integer(
        compute="_compute_tool_loan_count",
        store=True,
    )
    tool_loan_open_count = fields.Integer(
        compute="_compute_tool_loan_count",
        store=True,
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
        # Default filter on every Jobs list/kanban + the dashboard's default
        # view; index it like every other filtered boolean in this module.
        index=True,
    )

    # Smart-button counters. store=True — stage_log_count/done_count ride the
    # dashboard BOARD_FIELDS payload (200 jobs, 30s poll); store to avoid the
    # recurring recompute (deps already declared on the compute).
    stage_log_count = fields.Integer(
        compute="_compute_stage_log_count",
        store=True,
    )
    stage_log_done_count = fields.Integer(
        compute="_compute_stage_log_count",
        store=True,
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

    @api.depends("manifest_ids", "manifest_ids.create_date")
    def _compute_active_manifest(self):
        """The 'active' manifest is the most-recently-created one. v1
        spec assumes one manifest per job in the common case; we
        support multiple (re-delivery scenarios) by always picking the
        newest."""
        for rec in self:
            rec.manifest_id = rec.manifest_ids.sorted(
                key=lambda m: m.create_date or fields.Datetime.now(),
                reverse=True,
            )[:1].id if rec.manifest_ids else False

    @api.depends("manifest_id.state")
    def _compute_delivery_confirmed(self):
        for rec in self:
            rec.delivery_confirmed = rec.manifest_id.state in (
                "confirmed", "discrepancy",
            )

    @api.depends("damage_flag_ids.state", "damage_flag_ids.urgency")
    def _compute_is_blocked(self):
        for rec in self:
            rec.is_blocked = any(
                f.urgency == "blocking"
                and f.state not in ("resolved", "cancelled")
                for f in rec.damage_flag_ids
            )

    @api.depends("damage_flag_ids.state", "damage_flag_ids.urgency")
    def _compute_open_damage_count(self):
        for rec in self:
            open_flags = rec.damage_flag_ids.filtered(
                lambda f: f.state not in ("resolved", "cancelled")
            )
            rec.open_damage_count = len(open_flags)
            rec.blocking_damage_count = len(open_flags.filtered(
                lambda f: f.urgency == "blocking"
            ))

    @api.depends("closeout_ids")
    def _compute_closeout_id(self):
        for rec in self:
            # Unique constraint enforces ≤ 1; just take first.
            rec.closeout_id = rec.closeout_ids[:1].id if rec.closeout_ids else False

    @api.depends("closeout_id.state")
    def _compute_closeout_done(self):
        for rec in self:
            rec.closeout_done = rec.closeout_id.state == "complete"

    @api.depends("punchlist_ids")
    def _compute_punchlist_id(self):
        for rec in self:
            rec.punchlist_id = (
                rec.punchlist_ids[:1].id if rec.punchlist_ids else False
            )

    @api.depends(
        "punchlist_id.state",
        "punchlist_id.signature_data",
        "punchlist_id.signed_by_name",
    )
    def _compute_sign_off_received(self):
        for rec in self:
            rec.sign_off_received = (
                rec.punchlist_id.state == "complete"
                and bool(rec.punchlist_id.signature_data)
                and bool((rec.punchlist_id.signed_by_name or "").strip())
            )

    @api.depends("tool_loan_ids", "tool_loan_ids.returned")
    def _compute_tool_loan_count(self):
        for rec in self:
            rec.tool_loan_count = len(rec.tool_loan_ids)
            rec.tool_loan_open_count = len(
                rec.tool_loan_ids.filtered(lambda l: not l.returned)
            )

    @api.depends("gps_arrival_time", "gps_departure_time")
    def _compute_on_site_duration(self):
        for rec in self:
            if rec.gps_arrival_time and rec.gps_departure_time:
                delta = rec.gps_departure_time - rec.gps_arrival_time
                rec.on_site_duration_hrs = delta.total_seconds() / 3600.0
            else:
                rec.on_site_duration_hrs = 0.0

    @api.depends("is_blocked", "stage_is_terminal")
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

    def action_open_manifest(self):
        """Open or create the delivery manifest for this job. Lazy-
        creates a manifest record if none exists; auto-loads lines
        from kit_picking_id when present."""
        self.ensure_one()
        Manifest = self.env["southbrook.delivery.manifest"]
        manifest = self.manifest_id or Manifest.create({
            "job_id": self.id,
            "picking_id": self.kit_picking_id.id if self.kit_picking_id else False,
        })
        if (not manifest.line_ids
                and (self.kit_picking_id or manifest.picking_id)):
            manifest.action_load_from_picking()
        return {
            "type": "ir.actions.act_window",
            "name": _("Delivery Manifest"),
            "res_model": "southbrook.delivery.manifest",
            "res_id": manifest.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_damage_flags(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Damage Flags"),
            "res_model": "southbrook.damage.flag",
            "view_mode": "list,form",
            "domain": [("job_id", "=", self.id)],
            "context": {"default_job_id": self.id},
        }

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
        jobs._spawn_phase_logs()
        return jobs

    def _spawn_phase_logs(self):
        """Idempotent: creates one stage_log per active phase that is
        not already linked. Safe to call again after adding a new phase.

        Batched across the whole recordset: the active-phase list is
        queried once and a single Log.create() covers every job's missing
        logs (was one Phase.search + one Log.create per job)."""
        Log = self.env["southbrook.installer.stage.log"]
        active_phases = self.env["southbrook.installer.phase"].search(
            [("active", "=", True)]
        )
        vals_list = []
        for job in self:
            missing = active_phases - job.stage_log_ids.mapped("phase_id")
            vals_list += [
                {"job_id": job.id, "phase_id": phase.id}
                for phase in missing.sorted("sequence")
            ]
        if vals_list:
            Log.create(vals_list)

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

    def action_open_punchlist(self):
        """Open or create the punchlist for this job. Lazy-creates and
        moves to in_progress (which auto-spawns items from the
        configured templates)."""
        self.ensure_one()
        Punchlist = self.env["southbrook.installer.punchlist"]
        punchlist = self.punchlist_id or Punchlist.create({
            "job_id": self.id,
        })
        if punchlist.state == "draft":
            punchlist.action_open()
        return {
            "type": "ir.actions.act_window",
            "name": _("Punchlist"),
            "res_model": "southbrook.installer.punchlist",
            "res_id": punchlist.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_closeout(self):
        """Open or create the close-out record for this job. Lazy-
        creates and moves to in_progress (which auto-populates the
        tool return lines from job.tool_loan_ids)."""
        self.ensure_one()
        Closeout = self.env["southbrook.installer.closeout"]
        closeout = self.closeout_id or Closeout.create({
            "job_id": self.id,
        })
        if closeout.state == "draft":
            closeout.action_open()
        return {
            "type": "ir.actions.act_window",
            "name": _("Close-Out Checklist"),
            "res_model": "southbrook.installer.closeout",
            "res_id": closeout.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_tool_loans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tool Loans"),
            "res_model": "southbrook.installer.tool.loan",
            "view_mode": "list,form",
            "domain": [("job_id", "=", self.id)],
            "context": {"default_job_id": self.id},
        }
