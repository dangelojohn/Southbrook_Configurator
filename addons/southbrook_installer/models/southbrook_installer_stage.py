# SPDX-License-Identifier: LGPL-3.0-only
"""Workflow stages for southbrook.installer.job.

The stage model is canonical data — the eight stages live in
``data/southbrook_installer_stage_data.xml`` and are matched by
``code`` (a stable enum-like identifier). Code-level logic NEVER
matches by ``name`` (which is translatable).

Gate semantics: the boolean ``gate_*`` flags on each stage are the
**exit conditions** for that stage. To advance a job FROM stage X,
all of X's gates must be satisfied.
"""
from odoo import _, api, fields, models


class SouthbrookInstallerStage(models.Model):
    _name = "southbrook.installer.stage"
    _description = "Installer Job Workflow Stage"
    _order = "sequence, id"
    _rec_name = "name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Display name shown in statusbar and kanban columns.",
    )
    code = fields.Char(
        required=True,
        index=True,
        help="Stable enum identifier (e.g. SCHEDULED, "
             "INSTALLATION_IN_PROGRESS). Used by business logic; "
             "never translate or rename this without a migration.",
    )
    sequence = fields.Integer(
        default=10,
        index=True,
        help="Ordering across the stage workflow. The 'next stage' "
             "on advance is the stage with the lowest sequence > current.",
    )
    fold = fields.Boolean(
        default=False,
        help="Fold this column in kanban (terminal stages typically folded).",
    )
    description = fields.Text(
        translate=True,
        help="Operator-facing description: what work happens in this stage "
             "and what the exit gate is.",
    )

    # Exit-gate flags — checked when advancing AWAY from this stage.
    gate_require_delivery_confirmed = fields.Boolean(
        string="Gate: Delivery Confirmed",
        help="Cannot leave this stage until the job's delivery manifest "
             "is confirmed.",
    )
    gate_require_all_phases_done = fields.Boolean(
        string="Gate: All Install Phases Done",
        help="Cannot leave this stage until every active phase log on "
             "the job is in state 'done' or 'skipped'.",
    )
    gate_require_sign_off = fields.Boolean(
        string="Gate: Builder Sign-Off",
        help="Cannot leave this stage until builder sign-off is recorded "
             "on the job.",
    )
    gate_require_closeout_done = fields.Boolean(
        string="Gate: Close-Out Complete",
        help="Cannot leave this stage until the close-out checklist is "
             "submitted on the job.",
    )

    # Side-effect flags — let later phases react to entering this stage
    # (e.g. Phase 2.3 invoice trigger). Stored as data so the workflow
    # is configurable, not hard-coded.
    auto_create_invoice = fields.Boolean(
        help="When a job enters this stage, fire the invoice draft "
             "creation hook (wired in Phase 2.3).",
    )
    is_terminal = fields.Boolean(
        help="Marks the end of the workflow. Jobs in a terminal stage "
             "cannot be advanced further.",
    )
    color = fields.Integer(
        default=0,
        help="Kanban column color (Odoo standard palette 0-11).",
    )

    _name_uniq = models.Constraint(
        "unique(code)",
        "Stage code must be unique across the installer workflow.",
    )

    # Re-declared explicitly so our compute override binds to the field
    # in v19 (a bare method override without re-declaration silently
    # no-ops on the inherited `display_name`).
    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
        recursive=False,
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} ({rec.code})" if rec.code else (
                rec.name or _("New Stage")
            )

    def get_next_stage(self):
        """Return the next stage in sequence order, or empty recordset
        if this is the last stage."""
        self.ensure_one()
        return self.search(
            [("sequence", ">", self.sequence)],
            order="sequence asc, id asc",
            limit=1,
        )
