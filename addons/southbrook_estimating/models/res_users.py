# SPDX-License-Identifier: LGPL-3.0-only
"""
res.users extension — NF7 + NF8 per-user Order Builder preferences.

Both pure user-preference fields. No business logic, no schema change to
the order model. Views read these to conditionally reorder the inline
config drawer (NF8) or pre-populate attribute defaults (NF7).

NF7 — Amazing Window keyboard-first pattern (Case Study section 3.B):
  Most reps work primarily in one series. The default series field lets
  the rep skip a Tab — every new line starts with their default series
  selected. Persisted per user, defaults to Contractor (the 80% case).

NF8 — Pro Finish width-first pattern (Case Study section 3.C):
  When a rep is keying from a contractor's dimensioned drawing, width is
  the primary input. The mode field flips the inline drawer to surface
  width above family. View conditional only; no schema change to the
  order model.
"""
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # --- NF7 — default series for the Amazing Window keyboard-first flow ---
    southbrook_default_series = fields.Selection(
        selection=[
            ("contractor", "Contractor Series"),
            ("contemporary", "Contemporary"),
            ("elegance", "Elegance"),
            ("signature", "Signature"),
        ],
        string="Default Series",
        default="contractor",
        help=(
            "Pre-selected series on every new order line for this user. "
            "Defaults to Contractor (the 80% case per the Case Study). "
            "Reps who work primarily in another series set this once in "
            "their preferences and save a Tab on every line."
        ),
    )

    # --- NF8 — entry mode (family-first vs width-first) ---
    southbrook_order_entry_mode = fields.Selection(
        selection=[
            ("family_first", "Family First (Default)"),
            ("width_first", "Width First (Spec-Driven)"),
        ],
        string="Order-Entry Mode",
        default="family_first",
        help=(
            "Drives the inline config drawer layout in the Order Builder. "
            "family_first (default): family > width > attributes. "
            "width_first: width above family, suitable for the Pro Finish "
            "spec-driven workflow when keying from a contractor drawing."
        ),
    )
