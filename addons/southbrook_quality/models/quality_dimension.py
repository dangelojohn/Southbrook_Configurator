# SPDX-License-Identifier: LGPL-3.0-only
"""Master data: controlled vocabulary of measurable quality dimensions.

Each row is a (key, nominal, LSL, USL, UoM) tuple consumed by SPC sample
records and the rolled-up Cpk view. Keys are stable string handles so that
shop-floor flutter clients + REST consumers can reference a dimension
without knowing the Odoo record id.
"""

from odoo import fields, models


class SouthbrookQualityDimension(models.Model):
    _name = "southbrook.quality.dimension"
    _description = "Southbrook Quality Dimension (SPC controlled vocabulary)"
    _order = "key"

    key = fields.Char(
        string="Key",
        required=True,
        help="Stable handle, e.g. carcass_squareness_mm. Referenced by SPC samples.",
    )
    name = fields.Char(string="Name", required=True, translate=True)
    nominal = fields.Float(string="Nominal", required=True)
    usl = fields.Float(string="Upper Spec Limit (USL)", required=True)
    lsl = fields.Float(string="Lower Spec Limit (LSL)", required=True)
    uom_id = fields.Many2one("uom.uom", string="Unit of Measure")
    active = fields.Boolean(default=True)

    # v19: use models.Constraint instead of legacy _sql_constraints list.
    _unique_key = models.Constraint(
        "UNIQUE(key)",
        "Quality dimension key must be unique.",
    )
