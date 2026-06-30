# SPDX-License-Identifier: LGPL-3.0-only
"""11-phase installation sub-workflow template.

Each installer job auto-spawns one ``southbrook.installer.stage.log``
per active phase. The phase model itself is config — admins can
add/disable phases without touching code.
"""
from odoo import _, api, fields, models


class SouthbrookInstallerPhase(models.Model):
    _name = "southbrook.installer.phase"
    _description = "Installation Phase Template"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Stable enum identifier (PHASE_01 .. PHASE_11). Used by "
             "diagrams and BOM lookups; do not rename without migration.",
    )
    sequence = fields.Integer(default=10, index=True)
    description = fields.Text(
        translate=True,
        help="What the installer must complete in this phase.",
    )
    require_photo = fields.Boolean(
        default=True,
        help="When True, the per-job phase log cannot be marked 'done' "
             "until at least ``min_photos`` photos are attached.",
    )
    min_photos = fields.Integer(
        default=1,
        help="Minimum photo count to pass the photo gate. Ignored when "
             "require_photo=False.",
    )
    diagram_tag = fields.Char(
        help="Free-form tag used by Phase 4+ to filter relevant install "
             "drawings/BOM lines for this phase (e.g. 'upper_cabinet').",
    )
    estimated_duration_mins = fields.Integer(
        default=60,
        help="Planning estimate. Surfaced on the per-job phase log for "
             "comparison against actual duration.",
    )
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "unique(code)",
        "Phase code must be unique.",
    )
    _min_photos_nonneg = models.Constraint(
        "check (min_photos >= 0)",
        "Minimum photo count cannot be negative.",
    )

    # Re-declared so the compute override binds in v19.
    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
        recursive=False,
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code} — {rec.name}" if rec.code else (
                rec.name or _("New Phase")
            )
