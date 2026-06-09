# SPDX-License-Identifier: LGPL-3.0-only
"""Hardware-brand register — a small model so Odoo CE doesn't need OCA
product_brand and so the catalog can group SKUs by manufacturer (Blum,
Salice, Hettich, Marathon, etc.) for filtering and reporting.
"""
from odoo import fields, models


class SouthbrookHardwareBrand(models.Model):
    _name = "southbrook.hardware.brand"
    _description = "Southbrook Hardware Brand"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(
        index=True,
        help="Short brand code used in xml_ids and the hardware_map "
             "(e.g. 'blum', 'salice', 'hettich').",
    )
    active = fields.Boolean(default=True)
    note = fields.Text()

    _sql_constraints = [
        ("name_uniq", "unique(name)", "Brand name must be unique."),
        ("code_uniq", "unique(code)", "Brand code must be unique."),
    ]
