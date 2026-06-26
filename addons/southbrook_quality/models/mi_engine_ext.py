# SPDX-License-Identifier: LGPL-3.0-only
"""Manufacturing Intelligence quality tiles.

The base southbrook.mi.engine is an AbstractModel and Odoo 19 forbids
inheriting an AbstractModel as a concrete models.Model (registry raises
TypeError - see project memory note ``odoo19_abstract_model_inherit_trap``).
We therefore expose a NEW concrete model that the manager dashboard view
references for the four quality tiles. The model has no records of its
own; it is a stateless computed snapshot the view reads on render.
"""

from datetime import timedelta

from odoo import api, fields, models


class SouthbrookQualityMiTiles(models.Model):
    _name = "southbrook.quality.mi_tiles"
    _description = "Southbrook Quality MI Tiles (snapshot)"
    _rec_name = "label"

    label = fields.Char(default="Quality Tiles", required=True)
    quality_fpy_30d = fields.Float(
        compute="_compute_tiles",
        digits=(6, 4),
        string="First-Pass Yield (30d)",
    )
    quality_open_ncr_count = fields.Integer(
        compute="_compute_tiles",
        string="Open NCRs",
    )
    quality_critical_open_count = fields.Integer(
        compute="_compute_tiles",
        string="Open Critical NCRs",
    )
    quality_supplier_defect_rate_30d = fields.Float(
        compute="_compute_tiles",
        digits=(6, 4),
        string="Supplier Defect Rate (30d)",
    )

    @api.depends("label")
    def _compute_tiles(self):
        cutoff = fields.Datetime.now() - timedelta(days=30)
        Ncr = self.env["southbrook.ncr"]
        Production = self.env["mrp.production"]
        Defect = self.env["southbrook.quality.supplier_defect"]

        ncr_30d = Ncr.search_count([("create_date", ">=", cutoff)])
        prod_30d = Production.search_count([("create_date", ">=", cutoff)])
        open_ncr = Ncr.search_count(
            [("state", "in", ("draft", "quarantine", "rework"))]
        )
        critical_open = Ncr.search_count(
            [
                ("state", "in", ("draft", "quarantine", "rework")),
                ("severity", "=", "critical"),
            ]
        )

        defects = Defect.search([("create_date", ">=", cutoff)])
        total_defective = sum(d.quantity_defective for d in defects)
        total_received = sum(d.quantity_received for d in defects)
        supplier_rate = (
            total_defective / total_received if total_received else 0.0
        )

        fpy = (1.0 - (ncr_30d / prod_30d)) if prod_30d else 1.0

        for rec in self:
            rec.quality_fpy_30d = fpy
            rec.quality_open_ncr_count = open_ncr
            rec.quality_critical_open_count = critical_open
            rec.quality_supplier_defect_rate_30d = supplier_rate
