# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models
from .material_family import WEIGHT_SOURCES

# Estimation-grade family fallback densities (g/cm³), spec §14.4 (±15%).
FAMILY_DEFAULT_DENSITY = {
    "ewood": 0.68, "ewood_ply": 0.65, "swood": 0.70, "metal": 7.85,
    "plastic": 1.20, "glass": 2.50, "stone": 2.60, "concrete": 2.30,
}


class KitchenMaterial(models.Model):
    _inherit = "southbrook.kitchen.material"

    family_id = fields.Many2one("material.family", index=True)
    weight_source = fields.Selection(WEIGHT_SOURCES, default="density_volume")
    density = fields.Float(string="Density (g/cm³)", digits=(8, 3),
                           help="Effective density — estimation grade (±15%).")
    density_source = fields.Selection(
        [("material", "This material"), ("family_default", "Family default")],
        default="material")
    effective_density = fields.Float(compute="_compute_effective_density", digits=(8, 3))
    base_uom_id = fields.Many2one("uom.uom")
    facing = fields.Selection(
        [("none", "None"), ("paper", "Paper-faced"), ("fiberglass", "Fiberglass (DensGlass)")],
        default="none", help="Drywall/board facing.")
    waste_pct = fields.Float(string="Waste %")
    linear_density = fields.Float(string="Linear density (kg/m)", help="Edgebanding etc.")
    weight_per_unit = fields.Float(string="Weight per unit (kg)", help="Hardware etc.")
    thickness_mm = fields.Float(
        "Thickness (mm)", digits=(6, 3),
        help="Sheet thickness; e.g. 1/2\"=12.70, 5/8\"=15.875, 3/4\"=19.05. "
             "Overrides the cut-constant thickness in the weight calc when "
             "set.")
    # Cost cascade Tier-2 (manual) inputs — consumed by material.cost.source (Task 8).
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id)
    manual_unit_price = fields.Monetary(
        string="Manual Unit Price", currency_field="currency_id",
        help="Manual cost-basis override for the sourcing cascade (Tier 2).")

    @api.depends("density", "density_source", "family_id", "family_id.parent_id")
    def _compute_effective_density(self):
        for m in self:
            if m.density_source == "material" and m.density:
                m.effective_density = m.density
            else:
                # walk up to a known family default
                fam = m.family_id
                val = 0.0
                while fam and not val:
                    val = FAMILY_DEFAULT_DENSITY.get(fam.code, 0.0)
                    fam = fam.parent_id
                m.effective_density = val
