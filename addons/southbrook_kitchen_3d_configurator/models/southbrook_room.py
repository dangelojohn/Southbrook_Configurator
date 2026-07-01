# SPDX-License-Identifier: LGPL-3.0-only
"""Recommendation D — Sprint 1 bridge fields on southbrook.room.

Extends the existing southbrook.room (owned by southbrook_estimating)
with the 3D-scene-behavior fields that today live on
southbrook.kitchen.design. Once the reconciliation cron mirrors
designs → rooms, the 3D configurator can lift these controls off the
room record and retire the design model in Sprint 3.

`x_kitchen_image` keeps the `x_` Odoo prefix (it's an existing
manual-column takeover pattern — see migrations/19.0.4.19.0/
pre-migrate.py). All other new fields carry the `sb_` prefix for
provenance parity with existing `sb_width_mm`, `sb_bom_id`, etc.
"""

from odoo import fields, models


class SouthbrookRoom(models.Model):
    _inherit = "southbrook.room"

    # ── Room-behaviour settings that today live on
    #    southbrook.kitchen.design. Twin fields carry the same
    #    default + selection metadata; the reconciliation cron
    #    copies design values → room values one-way in Sprint 1.
    sb_soffit_height_mm = fields.Integer(
        string="Soffit Height (mm)",
        default=2134,   # 84"
        help="Bottom-of-soffit height (typical: 84\" ≈ 2134 mm for an "
             "8' ceiling with a 12\" soffit drop). Only consulted "
             "when sb_wall_cab_top_alignment is 'to_soffit'.",
    )
    sb_wall_cab_top_alignment = fields.Selection(
        selection=[
            ("fixed_gap",  "Fixed 18\" gap above counter"),
            ("to_ceiling", "Up to ceiling"),
            ("to_soffit",  "Up to soffit"),
        ],
        string="Wall Cabinet Top",
        default="fixed_gap",
        help="How wall cabinets align vertically. `fixed_gap` keeps "
             "the industry-standard 18\" gap between counter and wall "
             "cab bottom. `to_ceiling` raises wall cabs to touch the "
             "ceiling. `to_soffit` raises them to touch a soffit "
             "(reads sb_soffit_height_mm).",
    )
    sb_filler_strategy = fields.Selection(
        selection=[
            ("split",  "Split (half at each end)"),
            ("left",   "Left end only"),
            ("right",  "Right end only"),
            ("scribe", "None (carpenter scribes on site)"),
        ],
        string="Filler Placement",
        default="split",
        help="How the leftover width between cabinets and walls is "
             "handled. `split` places half-width fillers at both ends "
             "(most common). `scribe` skips fillers and asks the "
             "installer to scribe the end cabinet to the wall.",
    )
    x_kitchen_image = fields.Image(
        string="Kitchen Preview",
        help="Screenshot / render of the 3D kitchen layout for kanban + "
             "spec-sheet PDF. Named `x_` per the Odoo manual-column "
             "takeover convention already in use on southbrook.kitchen."
             "design.",
        max_width=800,
        max_height=600,
        attachment=True,
        store=True,
        copy=True,
    )
    sb_design_state = fields.Selection(
        selection=[
            ("draft",      "Draft"),
            ("configured", "Configured"),
            ("quoted",     "Quoted"),
            ("ordered",    "Ordered"),
        ],
        string="Design State",
        default="draft",
        tracking=True,
        help="Mirrors southbrook.kitchen.design.state during Rec D "
             "Sprint 1 for stage-pipeline continuity while the design "
             "model is deprecated.",
    )

    # ── Bridge back to the design record during Sprint 1
    sb_design_ids = fields.One2many(
        "southbrook.kitchen.design",
        "room_id",
        string="Bridged Kitchen Designs",
    )
