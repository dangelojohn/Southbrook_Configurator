# SPDX-License-Identifier: LGPL-3.0-only
"""Kitchen-cabinet substrate vocabulary.

Lightweight CE-safe master-data model so work centers can declare what
they can cut, edge-band, drill, sand, paint, or pack. Operation
templates (M2) use the same model to gate which templates are valid
for a given (material, finish) pair.

Kept deliberately small — no pricing, no GTIN, no vendor cross-refs —
to avoid colliding with `product.template` / `southbrook_hardware_brand` /
`southbrook_dims` substrate enums. The substrate ENUM in
`sb_cutlist.py` (melamine_white_5_8 etc.) is the geometric vocabulary;
this model is the SHOP-FLOOR vocabulary. The two will be cross-walked
in M4 when mrp.production picks up x_sbk_material_type.
"""
from odoo import fields, models


class SouthbrookKitchenMaterial(models.Model):
    _name = "southbrook.kitchen.material"
    _description = "Southbrook Kitchen Material"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True, translate=True)
    code = fields.Char(
        required=True, index=True,
        help="Stable short code used in xml_ids and reporting groupbys.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    requires_finishing = fields.Boolean(
        help="When True, parts of this material typically continue through "
             "sanding + paint/lacquer. Drives default operation-template "
             "routing in M2.",
    )
    can_be_edge_banded = fields.Boolean(
        default=True,
        help="False for solid wood and stone/quartz/solid-surface — they "
             "are profiled or polished, not edge-banded.",
    )
    is_subcontract_default = fields.Boolean(
        help="Stone / quartz / solid surface tops typically go to a "
             "subcontractor. Drives the default countertop routing.",
    )
    note = fields.Char(help="Free-form planning note.")

    _sql_constraints = [
        ("name_uniq", "unique(name)", "Material name must be unique."),
        ("code_uniq", "unique(code)", "Material code must be unique."),
    ]
