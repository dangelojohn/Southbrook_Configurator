# SPDX-License-Identifier: LGPL-3.0-only
"""Per-BoM-line material weight: weight_source dispatch + LOCKED conversion.

Task 6 (Southbrook Materials Phase-1). Adds `material_id`,
`component_volume_mm3` and `component_weight_kg` to `mrp.bom.line`, plus the
pure helpers `_weight_from_volume` / `_weight_for_qty` / `_panel_volume_mm3`.

LOCKED conversion (Global Constraint, verbatim from task-6-brief.md):
    weight_kg = effective_density(g/cm3) * volume_mm3 / 1_000_000
    then float_round(raw, precision_digits=2, rounding_method="HALF-UP")

--------------------------------------------------------------------------
`_panel_volume_mm3` integration point — INVESTIGATED, not guessed
--------------------------------------------------------------------------
`southbrook_estimating.mrp.bom._compute_panel_dimensions(width_mm, height_mm,
depth_mm, family="base", door_count=1, drawer_count=0, finished_sides="none")`
is `@api.model` and returns a dict (verified by reading the method body,
addons/southbrook_estimating/models/mrp_bom.py lines ~192-313):

    {"side_L": (L,W,T) | None, "side_R": (...), "top": (...), "bottom": (...),
     "back": (...), "shelf": (...) | None, "shelf_count": int,
     "door": (...) | None, "door_count": int, "drawer_count": int,
     "hinge_pair_count": int, "handle_count": int,
     "drawer_slide_pair_count": int, "edge_banding_length_mm": int}

There is NO "panels" key (the brief's illustrative snippet assumed one — it
was wrong; this is the actual, grep-verified shape). Each panel key holds
ONE tuple; "shelf" must be multiplied by "shelf_count" and "door" by
"door_count" to get total panel volume (family/finished_sides/drawer_count
only affect hardware counts and edge-banding, not panel volume, so they are
irrelevant to the weight computation).

The blocking problem is the OTHER half of the brief's instruction: finding
a reliable width_mm/height_mm/depth_mm for `line.bom_id`'s cabinet product.
Investigated and ruled out, in order:

1. `product.template` / `product.product` (southbrook_estimating models) —
   grepped `product_template.py`: no width_mm/height_mm/depth_mm field
   exists. The brief's stub code (`getattr(cab, "sb_width_mm", 0.0)`) refers
   to fields that do not exist anywhere in the codebase — confirmed by grep,
   not assumed.
2. Attribute-value route (`product_template_attribute_value_ids` ->
   `product_attribute_value_id.value_mm`, the same pattern already used by
   this file's sibling `_compute_southbrook_lead_time_extra`) — reliable
   for WIDTH only. `attr_width` is a real `product.attribute` shipped in
   `data/attributes.xml`. But `attr_height` and `attr_depth` are NOT: grep
   confirms no such `product.attribute` record is ever defined for height
   or depth. `product_config_line.py` looks them up via
   `ref(..., raise_if_not_found=False)`, which resolves to `False`/None
   for both, in the currently shipped data — so height_mm/depth_mm can
   never come from a variant attribute selection today.
3. `product_config_line.py` (`_SKU_DEFAULTS`, its own private dict, and the
   config-session-time-only computation at line ~99) is a wizard/session
   construct — not exposed as a stored, queryable field on the BoM's
   product, and not reachable from a `mrp.bom.line` compute without either
   duplicating a private table or invoking session state that may not
   exist (e.g. demo-seeded variants with no `product.config.session`).
4. `sale_order_line._sb_derive_dimensions` (a parallel best-effort resolver
   in the same codebase) is explicit about being "best-effort" and FABRICATES
   fallback height/depth from hardcoded family defaults when no attribute or
   name-parse hit is found. Mirroring it here would violate the "never
   fabricate dimensions" constraint of this task.

Conclusion: height_mm/depth_mm are not reliably obtainable at the
`mrp.bom.line` level today. Per the task brief's explicit fallback branch,
`_panel_volume_mm3` returns 0.0 and logs a debug note rather than fabricate.
`component_weight_kg` for `density_volume` materials is therefore honestly
"unavailable" (0.0) until a later phase adds a stored, config-time-populated
width_mm/height_mm/depth_mm field on the cabinet's product.template (the
natural home, since `_compute_panel_dimensions` is already invoked from
`product_config_line.py` at that exact moment — it would just need to also
write W/H/D back onto the template/variant it configures).

The pure helpers (`_weight_from_volume`, `_weight_for_qty`) and the
weight_source dispatch are fully implemented and unit-tested independent of
this cutlist-wiring gap.
"""
import logging

from odoo import api, fields, models
from odoo.tools import float_round

_logger = logging.getLogger(__name__)


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    material_id = fields.Many2one(
        "southbrook.kitchen.material",
        compute="_compute_material_id",
        store=True,
        help="Physical material this component resolves to, via the "
             "component product's 'Material' attribute value "
             "(product.product._resolve_material()).",
    )
    component_volume_mm3 = fields.Float(
        string="Component Volume (mm3)",
        compute="_compute_component_weight",
        store=True,
        help="Cabinet cutlist volume attributable to this component. "
             "0.0 when the volumetric source (cabinet width/height/depth) "
             "is unavailable — see _panel_volume_mm3 docstring.",
    )
    component_weight_kg = fields.Float(
        string="Weight (kg)",
        compute="_compute_component_weight",
        store=True,
        digits=(10, 2),
    )

    @api.depends("product_id")
    def _compute_material_id(self):
        for line in self:
            line.material_id = (
                line.product_id._resolve_material() if line.product_id else False
            )

    # ----------------------------------------------------------------
    # Pure helpers — LOCKED conversion + weight_source dispatch.
    # No ORM side effects; directly unit-testable (see
    # tests/test_weight_line.py).
    # ----------------------------------------------------------------
    def _weight_from_volume(self, material, volume_mm3):
        """LOCKED conversion (Global Constraint, exact):

        kg = effective_density(g/cm3) * volume_mm3 / 1_000_000, then
        float_round(raw, precision_digits=2, rounding_method="HALF-UP").
        """
        raw = material.effective_density * volume_mm3 / 1_000_000.0
        return float_round(raw, precision_digits=2, rounding_method="HALF-UP")

    def _weight_for_qty(self, material, volume_mm3, qty):
        """Dispatch on material.weight_source to a per-line weight (kg).

        - density_volume: _weight_from_volume(material, volume_mm3) * qty
        - linear_density: linear_density(kg/m) * qty, HALF-UP to 2dp
          (qty is interpreted as linear metres for linear materials)
        - per_unit: weight_per_unit(kg) * qty, HALF-UP to 2dp
        - density_area / none: 0.0 (Phase 1 — bought path, no volumetric
          weight)
        """
        src = material.weight_source
        if src == "density_volume":
            return self._weight_from_volume(material, volume_mm3) * qty
        if src == "linear_density":
            return float_round(
                material.linear_density * qty,
                precision_digits=2,
                rounding_method="HALF-UP",
            )
        if src == "per_unit":
            return float_round(
                material.weight_per_unit * qty,
                precision_digits=2,
                rounding_method="HALF-UP",
            )
        # density_area / none: no volumetric weight tracked in Phase 1.
        return 0.0

    # ----------------------------------------------------------------
    # Volume source — see the module docstring for the full investigation.
    # Returns 0.0 (never fabricated) whenever the cabinet's width/height/
    # depth cannot be read from real, stored data.
    # ----------------------------------------------------------------
    def _panel_volume_mm3(self, line):
        """Total cut-panel volume (mm3) for the CABINET `line` belongs to.

        Reliably available only when:
        1. `mrp.bom._compute_panel_dimensions` exists (southbrook_estimating
           installed), AND
        2. the cabinet's width_mm/height_mm/depth_mm are readable as real
           stored data (not fabricated defaults).

        As of this commit, (2) never holds — see the module docstring for
        the investigated reasons (no stored W/H/D field on
        product.template/product.product; height/depth have no backing
        product.attribute at all in shipped data). Returns 0.0 and logs a
        debug note documenting the exact gap, rather than guess.
        """
        Bom = self.env["mrp.bom"]
        if not hasattr(Bom, "_compute_panel_dimensions"):
            _logger.debug(
                "_panel_volume_mm3: southbrook_estimating not installed "
                "(mrp.bom._compute_panel_dimensions missing) — bom line %s "
                "gets 0.0 mm3.", line.id,
            )
            return 0.0

        cab = line.bom_id.product_tmpl_id
        # See module docstring: no reliable, non-fabricated source for
        # width_mm/height_mm/depth_mm exists yet at the mrp.bom.line level.
        # A future phase should have product.config.line write these back
        # onto the configured product.template/product.product at the same
        # moment it calls _compute_panel_dimensions() for the cutlist, so
        # this method can read them as plain stored fields.
        _logger.debug(
            "_panel_volume_mm3: no reliable width_mm/height_mm/depth_mm "
            "source for cabinet template %s (bom line %s) — see "
            "sb_material_mrp/models/mrp_bom.py module docstring for the "
            "investigated integration gap. Returning 0.0 (not fabricated).",
            cab.id, line.id,
        )
        return 0.0

    @api.depends(
        "material_id",
        "product_qty",
        "material_id.weight_source",
        "material_id.effective_density",
        "material_id.linear_density",
        "material_id.weight_per_unit",
    )
    def _compute_component_weight(self):
        for line in self:
            m = line.material_id
            if not m:
                line.component_volume_mm3 = 0.0
                line.component_weight_kg = 0.0
                continue
            vol = (
                self._panel_volume_mm3(line)
                if m.weight_source == "density_volume"
                else 0.0
            )
            line.component_volume_mm3 = vol
            line.component_weight_kg = self._weight_for_qty(m, vol, line.product_qty)


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    material_weight_total = fields.Float(
        string="Total Material Weight (kg)",
        compute="_compute_material_weight_total",
        digits=(10, 2),
        help="Sum of leaf-component weights, flattened via native "
             "bom.explode() so nested/phantom sub-assembly BoMs are "
             "counted once regardless of nesting depth (Task 7).",
    )

    @api.depends(
        "bom_line_ids.component_weight_kg",
        "bom_line_ids.material_id",
        "product_id",
        "product_qty",
    )
    def _compute_material_weight_total(self):
        for bom in self:
            total = 0.0
            # explode to leaves so nested/phantom BoMs are flattened (blindspot #5)
            _boms, lines = bom.explode(
                bom.product_id or bom.product_tmpl_id.product_variant_id,
                bom.product_qty,
            )
            for line, data in lines:
                m = line.material_id
                if not m:
                    continue
                qty = data.get("qty", line.product_qty)
                vol = (
                    line._panel_volume_mm3(line)
                    if m.weight_source == "density_volume"
                    else 0.0
                )
                total += line._weight_for_qty(m, vol, qty)
            bom.material_weight_total = float_round(
                total, precision_digits=2, rounding_method="HALF-UP"
            )
