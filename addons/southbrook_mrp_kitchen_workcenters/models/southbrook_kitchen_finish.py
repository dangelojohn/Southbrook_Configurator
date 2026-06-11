# SPDX-License-Identifier: LGPL-3.0-only
"""Kitchen-cabinet finish vocabulary.

Vocabulary the shop floor uses for "how does this surface go out the
door." Operation templates (M2) read `cure_time_buffer_min` so painted
/ lacquered parts get scheduled with the correct flow-time padding
through Cure / Dry Room (workcenter CURE).
"""
from odoo import fields, models


class SouthbrookKitchenFinish(models.Model):
    _name = "southbrook.kitchen.finish"
    _description = "Southbrook Kitchen Finish"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True, translate=True)
    code = fields.Char(
        required=True, index=True,
        help="Stable short code used in xml_ids and reporting groupbys.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    requires_sanding = fields.Boolean(
        default=True,
        help="Drives operation-template gating: painted / lacquered / "
             "stained finishes need sanding upstream; raw / melamine / "
             "laminate do not.",
    )
    requires_paint_booth = fields.Boolean(
        help="True for painted / lacquered / stained surfaces routed "
             "through PAINT.",
    )
    cure_time_buffer_min = fields.Integer(
        default=0,
        help="Minutes of cure/dry-room buffer to add to a part's flow "
             "time after the paint booth. 0 for non-wet finishes.",
    )
    finish_complexity_factor = fields.Float(
        default=1.0,
        help="Multiplier the duration formula applies to wet-finish work "
             "(more coats / longer flash time → higher factor). 1.0 for "
             "standard paint, 1.5 for high-gloss, 1.3 for lacquered.",
    )
    note = fields.Char(help="Free-form planning note.")

    _sql_constraints = [
        ("name_uniq", "unique(name)", "Finish name must be unique."),
        ("code_uniq", "unique(code)", "Finish code must be unique."),
    ]
