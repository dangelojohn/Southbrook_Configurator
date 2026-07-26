# SPDX-License-Identifier: LGPL-3.0-only
from odoo import api, fields, models
from .material_family import WEIGHT_SOURCES

# Estimation-grade family fallback densities (g/cm³), spec §14.4 (±15%).
FAMILY_DEFAULT_DENSITY = {
    "ewood": 0.68, "ewood_ply": 0.65, "swood": 0.70, "metal": 7.85,
    "plastic": 1.20, "glass": 2.50, "stone": 2.60, "concrete": 2.30,
}

# Task C2: dual-unit (metric + Imperial) dimensions. Canonical unit is always
# mm; the Imperial fields are computed-with-inverse companions so a Canadian
# shop can enter/read either unit on any record without losing precision.
MM_PER_IN = 25.4

# Standard sheet-good thicknesses (quick-pick), in canonical mm.
STANDARD_THICKNESS_MM = {
    "quarter": 6.35, "half": 12.70, "five_eighth": 15.875, "three_quarter": 19.05,
}


def _mm_to_in(mm):
    """mm -> in, rounded to 3dp to avoid float drift (e.g. 0.7499999...)."""
    return round(mm / MM_PER_IN, 3) if mm else 0.0


def _in_to_mm(inch):
    """in -> mm, rounded to 2dp (canonical mm precision)."""
    return round(inch * MM_PER_IN, 2) if inch else 0.0


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
    # Task C2: canonical mm sheet-size fields.
    sheet_width_mm = fields.Float("Sheet Width (mm)", digits=(8, 2), default=0.0)
    sheet_height_mm = fields.Float("Sheet Height (mm)", digits=(8, 2), default=0.0)

    # Task C2: Imperial companions — computed-with-inverse. The compute reads
    # the canonical mm field (one-directional dependency); the inverse writes
    # the mm field when the Imperial field is assigned. There is no in<->in
    # dependency, so a write can never re-trigger its own inverse (no loop).
    thickness_in = fields.Float(
        "Thickness (in)", digits=(8, 3), store=True,
        compute="_compute_thickness_in", inverse="_inverse_thickness_in",
        help="Imperial companion of thickness_mm. Editing either field "
             "updates the other; thickness_mm remains canonical.")
    sheet_width_in = fields.Float(
        "Sheet Width (in)", digits=(8, 3), store=True,
        compute="_compute_sheet_width_in", inverse="_inverse_sheet_width_in",
        help="Imperial companion of sheet_width_mm.")
    sheet_height_in = fields.Float(
        "Sheet Height (in)", digits=(8, 3), store=True,
        compute="_compute_sheet_height_in", inverse="_inverse_sheet_height_in",
        help="Imperial companion of sheet_height_mm.")

    standard_thickness = fields.Selection(
        [("quarter", '1/4" (6.35mm)'), ("half", '1/2" (12.70mm)'),
         ("five_eighth", '5/8" (15.875mm)'), ("three_quarter", '3/4" (19.05mm)')],
        string="Standard Thickness",
        help="Quick-pick; selecting a value sets thickness_mm to the exact "
             "standard equivalent. Purely a convenience — thickness_mm/in "
             "remain the source of truth and can still be hand-edited.")

    @api.depends("thickness_mm")
    def _compute_thickness_in(self):
        for m in self:
            m.thickness_in = _mm_to_in(m.thickness_mm)

    def _inverse_thickness_in(self):
        for m in self:
            m.thickness_mm = _in_to_mm(m.thickness_in)

    @api.depends("sheet_width_mm")
    def _compute_sheet_width_in(self):
        for m in self:
            m.sheet_width_in = _mm_to_in(m.sheet_width_mm)

    def _inverse_sheet_width_in(self):
        for m in self:
            m.sheet_width_mm = _in_to_mm(m.sheet_width_in)

    @api.depends("sheet_height_mm")
    def _compute_sheet_height_in(self):
        for m in self:
            m.sheet_height_in = _mm_to_in(m.sheet_height_mm)

    def _inverse_sheet_height_in(self):
        for m in self:
            m.sheet_height_mm = _in_to_mm(m.sheet_height_in)

    @api.onchange("standard_thickness")
    def _onchange_standard_thickness(self):
        if self.standard_thickness:
            self.thickness_mm = STANDARD_THICKNESS_MM[self.standard_thickness]

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
