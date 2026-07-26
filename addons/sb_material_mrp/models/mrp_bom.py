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

Conclusion (AS OF THIS TASK — historical, gap now CLOSED, see below):
height_mm/depth_mm were not reliably obtainable at the `mrp.bom.line` level.
Per the task brief's explicit fallback branch, `_panel_volume_mm3` returned
0.0 and logged a debug note rather than fabricate. `component_weight_kg` for
`density_volume` materials was therefore honestly "unavailable" (0.0) until
a later phase added a stored, config-time-populated width_mm/height_mm/
depth_mm field on the cabinet's product.template/product.product.

--------------------------------------------------------------------------
UPDATE — Task A4 (Materials geometry-writeback plan): gap CLOSED
--------------------------------------------------------------------------
Exactly the "later phase" anticipated above has landed: Task A1 added
`product.product.sb_width_mm/sb_height_mm/sb_depth_mm/sb_panel_family/
sb_door_count/sb_drawer_count/sb_finished_sides` plus a reader,
`_sb_geometry_inputs()`, returning a dict of the exact kwargs
`_compute_panel_dimensions()` expects (or `{}` when the variant has no real
geometry). Tasks A2/A3 populate those fields at OCA variant-creation time
and via a one-off backfill. `_panel_volume_mm3` (below) now reads the
CABINET variant off `line.bom_id` (not the component `line.product_id`),
calls `_sb_geometry_inputs()`, and — when non-empty — calls
`_compute_panel_dimensions(**geo)` and sums the CARCASS panels (side_L,
side_R, top, bottom, back, shelf x shelf_count). Doors are excluded (a door
is normally a different material than the carcass sheet good this
`density_volume` component represents); a later precision pass can map
panel-type -> material explicitly. The honesty contract is unchanged: 0.0,
never fabricated, whenever geometry is genuinely absent.

The pure helpers (`_weight_from_volume`, `_weight_for_qty`) and the
weight_source dispatch remain independent of this wiring and unaffected.
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

    # Task B1: Per-line geometry override fields (Increment B)
    sb_line_width_mm = fields.Integer(
        string="Override Width (mm)",
        default=0,
        help="Per-line geometry override: width in mm. 0 = use variant geometry.",
    )
    sb_line_height_mm = fields.Integer(
        string="Override Height (mm)",
        default=0,
        help="Per-line geometry override: height in mm. 0 = use variant geometry.",
    )
    sb_line_depth_mm = fields.Integer(
        string="Override Depth (mm)",
        default=0,
        help="Per-line geometry override: depth in mm. 0 = use variant geometry.",
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
            # FIX-C (repair wave 1, finding #12) — `_weight_from_volume`
            # only rounds the PER-UNIT weight; multiplying by a
            # fractional `qty` can reintroduce more than 2 decimal
            # places (e.g. 2.815kg * 2.5 = 7.0375). The linear_density
            # and per_unit branches below both apply a final HALF-UP
            # 2dp round to their qty-multiplied result — mirror that
            # here so all three branches return the same LOCKED
            # precision contract (module docstring, line 10).
            return float_round(
                self._weight_from_volume(material, volume_mm3) * qty,
                precision_digits=2,
                rounding_method="HALF-UP",
            )
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
    def _panel_volume_mm3(self, line, _dims_cache=None):
        """Total CARCASS panel volume (mm3) for the cabinet `line` belongs to.

        `_dims_cache` (FIX-D, repair wave 1, finding #9) — optional dict
        passed in by a caller iterating many lines in one compute pass
        (e.g. `_compute_component_weight`, `_compute_material_weight_
        total`'s exploded-lines loop). Lines belonging to the same BoM
        share identical cabinet geometry, so `_compute_panel_dimensions`
        would otherwise be re-solved with byte-identical inputs once per
        line. Keyed on the exact resolved `geo` dict (sorted items
        tuple) so behavior is unchanged — a cache hit returns the exact
        same `dims` a fresh call would have produced. Local dict, scoped
        to a single compute pass; NOT an `ormcache` (no cross-request
        staleness risk). `None` (the default) disables caching entirely
        for any caller that doesn't opt in.

        Task A4 (Materials geometry-writeback plan): the gap documented in
        the module docstring above is closed — `product.product`
        (southbrook_estimating, Task A1) now carries stored
        sb_width_mm/sb_height_mm/sb_depth_mm/sb_panel_family/sb_door_count/
        sb_drawer_count/sb_finished_sides, populated at variant-creation and
        backfill time (Tasks A2/A3). `_sb_geometry_inputs()` exposes them as
        the exact kwargs `mrp.bom._compute_panel_dimensions()` expects, or
        `{}` when the variant has no real (non-fabricated) geometry — the
        honesty contract is unchanged, just the source of truth moved from
        "nothing" to "the stored variant fields".

        Sums l*w*th over the CARCASS-only panel keys returned by
        `_compute_panel_dimensions`: side_L, side_R, top, bottom, back, and
        shelf (multiplied by shelf_count). Doors are deliberately EXCLUDED —
        a door is typically a different material (e.g. 5-piece MDF vs.
        carcass melamine) than the density_volume component this method is
        computing volume for; a later precision pass should map
        panel-type -> material explicitly instead of lumping doors into the
        carcass sheet-good total.

        Returns 0.0 (never fabricated) when either:
        1. `mrp.bom._compute_panel_dimensions` doesn't exist
           (southbrook_estimating not installed — soft-guard, even though
           it's a hard manifest dependency of this module today), or
        2. the cabinet variant has no stored geometry
           (`_sb_geometry_inputs()` returns `{}`).
        """
        Bom = self.env["mrp.bom"]
        if not hasattr(Bom, "_compute_panel_dimensions"):
            _logger.debug(
                "_panel_volume_mm3: southbrook_estimating not installed "
                "(mrp.bom._compute_panel_dimensions missing) — bom line %s "
                "gets 0.0 mm3.", line.id,
            )
            return 0.0

        cab = line.bom_id.product_id or line.bom_id.product_tmpl_id.product_variant_id
        base_geo = cab._sb_geometry_inputs() if hasattr(cab, "_sb_geometry_inputs") else {}

        # Task B2 (Materials geometry-writeback plan, Increment B): a
        # per-line geometry override (mrp.bom.line.sb_line_width_mm/
        # sb_line_height_mm/sb_line_depth_mm, Task B1) wins over the
        # variant's own geometry, but ONLY when all three are set (>0) —
        # a partial override is not a real override and falls back to the
        # variant (A4 behavior), preserving the honesty contract. When the
        # override does apply, only width/height/depth are replaced; the
        # variant's family/door_count/drawer_count/finished_sides are kept
        # so panel-count-driven hardware/edge-banding stays correct.
        line_geo = {}
        if line.sb_line_width_mm and line.sb_line_height_mm and line.sb_line_depth_mm:
            line_geo = {
                **base_geo,
                "width_mm": line.sb_line_width_mm,
                "height_mm": line.sb_line_height_mm,
                "depth_mm": line.sb_line_depth_mm,
            }
        geo = line_geo or base_geo
        if not geo:
            _logger.debug(
                "_panel_volume_mm3: no geometry on variant %s (line %s) -> "
                "0.0 (not fabricated).", cab.id, line.id,
            )
            return 0.0

        if _dims_cache is None:
            dims = Bom._compute_panel_dimensions(**geo)
        else:
            cache_key = tuple(sorted(geo.items()))
            dims = _dims_cache.get(cache_key)
            if dims is None:
                dims = Bom._compute_panel_dimensions(**geo)
                _dims_cache[cache_key] = dims

        # Task C1 (weight-accuracy refinement): when the line's resolved
        # material carries a real sheet thickness (sb_material_core,
        # southbrook.kitchen.material.thickness_mm > 0), that thickness
        # OVERRIDES the fixed cut-constant thickness (`box_th`, baked into
        # `p[2]` by _compute_panel_dimensions) for the BOX panels only —
        # side_L, side_R, top, bottom, shelf. This makes a 1/2" carcass
        # weigh less than a 3/4" carcass built from the identical cabinet
        # geometry, instead of both being pinned to the same cut constant.
        #
        # The BACK panel is deliberately EXCLUDED from this override and
        # keeps its own returned thickness (`p[2]`, i.e. `back_th`) — a
        # cabinet back is typically a different, thinner material (e.g.
        # 1/4" ply/hardboard) than the box sheet good this `material_id`
        # represents, mirroring the existing door-exclusion rationale above.
        # Mapping each panel role to its OWN resolved material (so back/door
        # thickness could likewise come from a material field) is a
        # documented follow-up, not solved here.
        #
        # Fallback (honesty contract, unchanged): when thickness_mm is 0.0/
        # unset, box panels keep using the returned `p[2]` (pre-Task-C1 / A4
        # behavior) — never fabricated, never silently defaulted to a
        # made-up constant.
        mat_thickness_mm = (
            line.material_id.thickness_mm if line.material_id else 0.0
        )

        total = 0.0
        for key in ("side_L", "side_R", "top", "bottom"):
            p = dims.get(key)
            if p:
                th = mat_thickness_mm if mat_thickness_mm > 0 else p[2]
                total += p[0] * p[1] * th
        back = dims.get("back")
        if back:
            total += back[0] * back[1] * back[2]
        shelf = dims.get("shelf")
        if shelf:
            th = mat_thickness_mm if mat_thickness_mm > 0 else shelf[2]
            total += shelf[0] * shelf[1] * th * (dims.get("shelf_count") or 0)
        return total

    @api.depends(
        "material_id",
        "product_qty",
        "material_id.weight_source",
        "material_id.effective_density",
        "material_id.linear_density",
        "material_id.weight_per_unit",
        "material_id.thickness_mm",
        # Finding I-2 (final review, 2026-07-24) — best-effort depends so a
        # future direct edit of the cabinet's geometry or this line's
        # override retriggers the stored weight. Only covers the
        # `bom_id.product_id` (variant-BoM) path — `_panel_volume_mm3`
        # also falls back to `bom_id.product_tmpl_id.product_variant_id`
        # when `product_id` is unset, and that fallback path can't be
        # expressed as a static dotted depends here (it's a runtime `or`
        # on two different fields, not a stored relation Odoo's
        # dependency graph can walk). The REQUIRED fix for the documented
        # staleness (A3 backfill onto a PRE-EXISTING variant) is the
        # targeted recompute at the end of
        # `product.product._sb_backfill_geometry()` — this depends list
        # is the best-effort half for direct edits going forward.
        #
        # DOCUMENT-ONLY (repair wave 1, findings #6/#8, confirmed) —
        # `_sb_recompute_dependent_bom_weights()`'s search now ALSO
        # matches template-level BoM lines via `bom_id.product_tmpl_id.
        # product_variant_id` (FIX-B), so the backfill path is covered.
        # What remains UN-covered, by design, per the above: a direct
        # form/API edit to a template's variant[0] geometry (bypassing
        # `_sb_backfill_geometry()` entirely) still won't retrigger this
        # stored field, because @api.depends genuinely cannot express
        # the runtime fallback. No exotic depends attempted here — see
        # the reasons above.
        "sb_line_width_mm",
        "sb_line_height_mm",
        "sb_line_depth_mm",
        "bom_id.product_id.sb_width_mm",
        "bom_id.product_id.sb_height_mm",
        "bom_id.product_id.sb_depth_mm",
        "bom_id.product_id.sb_panel_family",
        "bom_id.product_id.sb_door_count",
        "bom_id.product_id.sb_drawer_count",
        "bom_id.product_id.sb_finished_sides",
    )
    def _compute_component_weight(self):
        # FIX-D (repair wave 1, finding #9) — one cache dict for this
        # whole compute pass; lines sharing a `bom_id` (and therefore
        # identical cabinet geometry) hit the cache instead of re-
        # solving `_compute_panel_dimensions` redundantly.
        dims_cache = {}
        for line in self:
            m = line.material_id
            if not m:
                line.component_volume_mm3 = 0.0
                line.component_weight_kg = 0.0
                continue
            vol = (
                self._panel_volume_mm3(line, _dims_cache=dims_cache)
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
            # FIX-D (repair wave 1, finding #9) — cache scoped to this
            # single bom's explode loop; see _panel_volume_mm3 docstring.
            dims_cache = {}
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
                    line._panel_volume_mm3(line, _dims_cache=dims_cache)
                    if m.weight_source == "density_volume"
                    else 0.0
                )
                total += line._weight_for_qty(m, vol, qty)
            bom.material_weight_total = float_round(
                total, precision_digits=2, rounding_method="HALF-UP"
            )
