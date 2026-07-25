# SPDX-License-Identifier: LGPL-3.0-only
"""MO material totals: weight, scrap, weight-to-purchase, cascaded cost,
provenance, and a cost-snapshot-with-refresh action.

Task 9 (Southbrook Materials Phase-1). Consumes `mrp.bom.material_weight_total`
(Task 7) and `material.cost.source._resolve` (Task 8, the vendor -> manual ->
online cascade resolver).
"""
from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    material_weight_total = fields.Float(
        string="Material Weight (kg)",
        compute="_compute_material_totals",
        digits=(10, 2),
        help="Rolled-up leaf-component weight from the MO's BoM "
             "(mrp.bom.material_weight_total).",
    )
    scrap_factor = fields.Float(
        string="Scrap %",
        default=0.0,
        help="Percentage allowance added on top of material_weight_total "
             "to get the weight to actually purchase.",
    )
    weight_to_purchase = fields.Float(
        string="Weight to Purchase (kg)",
        compute="_compute_material_totals",
        digits=(10, 2),
    )
    company_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id",
        string="Company Currency",
    )
    material_cost_total = fields.Monetary(
        string="Material Cost",
        compute="_compute_material_totals",
        currency_field="company_currency_id",
        help="Sum over move_raw_ids of material.cost.source._resolve() unit "
             "price times quantity. Phase-1 is single-currency: this sums "
             "unit_price values as-is in the company currency; converting "
             "each row's own currency_id is a documented later-phase item "
             "(see _compute_material_totals).",
    )
    cost_provenance = fields.Char(
        string="Cost Provenance",
        compute="_compute_material_totals",
        help="Merged, sorted-unique summary of the cost tiers behind "
             "material_cost_total (e.g. 'manual · vendor'). Surfaces "
             "'online' whenever any component's price is an unpriced "
             "placeholder — never hides it.",
    )
    cost_snapshot_date = fields.Date(
        string="Cost Snapshot Date",
        help="Stamped only by action_refresh_material_prices() — the date "
             "the cascaded cost was last (re)pulled.",
    )

    def _weight_to_purchase(self, weight_total, scrap_pct):
        """weight_total inflated by scrap_pct percent, HALF-even round to 2dp."""
        return round(weight_total * (1.0 + (scrap_pct or 0.0) / 100.0), 2)

    def _merge_provenance(self, rows):
        """Join the sorted, de-duplicated set of cost tiers found in `rows`.

        Deliberately surfaces "online" (the unpriced-placeholder tier)
        whenever even one line resolved to it — the whole point being that a
        mix of trusted and untrusted tiers must never read as fully trusted.
        """
        tiers = sorted({r.get("tier", "online") for r in rows})
        return " · ".join(tiers)

    @api.depends(
        "bom_id",
        "bom_id.material_weight_total",
        "move_raw_ids.product_id",
        "move_raw_ids.product_uom_qty",
        "scrap_factor",
    )
    def _compute_material_totals(self):
        Src = self.env["material.cost.source"]
        for mo in self:
            weight = mo.bom_id.material_weight_total if mo.bom_id else 0.0
            rows = []
            cost = 0.0
            for move in mo.move_raw_ids:
                if not move.product_id:
                    continue
                row = Src._resolve(move.product_id, move.product_uom_qty)
                rows.append(row)
                # Phase-1 is single-currency: unit_price is summed as-is in
                # the company currency. Converting row["currency_id"] to
                # company currency (multi-currency vendor prices) is a
                # documented later-phase item, not implemented here.
                cost += row["unit_price"] * move.product_uom_qty
            mo.material_weight_total = weight
            mo.weight_to_purchase = mo._weight_to_purchase(weight, mo.scrap_factor)
            mo.material_cost_total = cost
            mo.cost_provenance = mo._merge_provenance(rows) if rows else ""

    def action_refresh_material_prices(self):
        """Snapshot-with-refresh: stamp today's date, then recompute so the
        cascade re-pulls current vendor/manual prices."""
        self.cost_snapshot_date = fields.Date.context_today(self)
        self._compute_material_totals()
        return True
