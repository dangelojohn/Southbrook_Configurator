# SPDX-License-Identifier: LGPL-3.0-only
from odoo import fields, models

# Vocabulary MUST match sb.cutlist.PANEL_NAMES (southbrook_kitchen_mrp) so the
# post-MO cutlist can converge onto this material<->role link later.
PANEL_ROLE_KEYS = ("side_L", "side_R", "top", "bottom", "back", "shelf", "door")


class SbPanelRole(models.Model):
    _name = "sb.panel.role"
    _description = "Cabinet Panel Role"
    _order = "sequence, code"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)

    _unique_code = models.Constraint("unique(code)", "Panel role code must be unique.")
