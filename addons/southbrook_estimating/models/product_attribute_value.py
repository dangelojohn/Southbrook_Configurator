# SPDX-License-Identifier: LGPL-3.0-only
"""
Extend product.attribute.value with three Southbrook-specific fields:
  - value_inches / value_mm  (Q4 dual storage — dimensional values only)
  - lead_time_extra          (Q3 — manufacturing lead-time bump; maple box = +14d)

This file IS custom routine #4 per Build Spec §4. Adding any further
field to the same model requires PUNCHLIST justification.

NF11 — divergence from Q3 wording. Q3 said "add lead_time_extra field on
product.template.attribute.value" (the per-template variant); we put it on
product.attribute.value (the master) instead. Rationale:
  - Maple box is always +2 weeks regardless of template. There's no
    per-template variation to capture.
  - Mirrors price_extra in MECHANIC (the rollup pattern), but not in
    schema location. price_extra lives on the variant for historical
    Odoo reasons + edge cases that don't apply to Southbrook lead time.
  - Phase-1 seeding is dramatically simpler — set once on the master,
    every template that uses the attribute inherits the value via BoM rollup.
  - If Phase 2 surfaces a real need for per-template lead-time override,
    add a sibling field on product.template.attribute.value with a
    computed default from master. YAGNI for Phase 1.
"""
from odoo import fields, models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    # --- Q4 · Dual dimension storage ------------------------------------
    # Both fields are populated only for values on dimensional attributes
    # (width, height, depth). Non-dimensional values (series, finish,
    # door_style, etc.) leave both null.
    #
    # CRITICAL: never compute one from the other. North-American cabinetry
    # spec rounds differently than literal mm conversion. The workbook
    # specifies both; we capture both verbatim from #5 Price Master.
    value_inches = fields.Float(
        string="Value (in)",
        digits=(6, 3),
        help=(
            "Imperial display value used by the Order Builder (sales-rep mode) "
            "and exposed in workbook-equivalent UI."
        ),
    )
    value_mm = fields.Integer(
        string="Value (mm)",
        help=(
            "Canonical numeric value used by the parametric BoM rollup "
            "(_compute_panel_dimensions) and by the Phase-3 Three.js "
            "BufferGeometry layer. Set explicitly per the workbook spec."
        ),
    )

    # --- Q3 · Lead-time extra ------------------------------------------
    # Unit = days (matching Odoo's produce_delay convention).
    # Maple box: 14.0 (i.e. +2 weeks per Mapping §3.5).
    # Roll-up into produce_delay happens in mrp.bom (commit 5 / 8).
    lead_time_extra = fields.Float(
        string="Extra Lead Time (days)",
        default=0.0,
        help=(
            "Additional manufacturing lead time added when this attribute "
            "value is selected. Mirrors price_extra in mechanic. "
            "Maple box: 14.0 (+2 weeks). Roll-up happens in mrp.bom."
        ),
    )
