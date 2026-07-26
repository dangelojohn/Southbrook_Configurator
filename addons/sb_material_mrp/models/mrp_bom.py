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

--------------------------------------------------------------------------
UPDATE — sibling weight-attribution fix (live defect, 2026-07-26)
--------------------------------------------------------------------------
`_panel_volume_mm3` (below) resolves and returns the FULL carcass volume
for the cabinet `line.bom_id` belongs to — that has always been correct
for a configurator-built BoM, which has exactly ONE density_volume sheet
line per cabinet. It is WRONG for a hand-built/imported BoM that lists the
same sheet product on several per-panel lines (observed live: BoM 256, 5x
SBK-SHEET-MB34-WW; BoMs 280-286, several sheet lines each) — every such
line got the WHOLE carcass, over-counting the BoM's total material weight
by roughly the sibling count (live: ~5-6x, e.g. B24 = 247.98 kg vs a
realistic ~35-40 kg).

The fix does NOT change `_panel_volume_mm3` itself (every existing direct
caller/test of it keeps getting the raw, undivided carcass volume for the
line's own geometry — override-aware, byte-identical). Instead, the two
integration points that turn a volume into a stored/rolled-up weight
(`_compute_component_weight` and `_compute_material_weight_total`'s
explode loop) now route density_volume lines through a new wrapper,
`_sb_component_share_volume_mm3`, which divides that line's own carcass
volume by the total `product_qty` of every density_volume-resolving
SIBLING line on the same `bom_id` (itself included) — an estimation-grade,
product_qty-weighted attribution. This is Phase-2 cutlist territory to
solve precisely (which physical panel is which line); the invariant this
fix guarantees for Phase 1 is: **the BoM's total material weight counts
the carcass exactly once**, however many sibling lines happen to
reference it. A single density_volume line is its own only sibling, so
its share is 100% and its stored weight is unchanged.
"""
import logging
import math

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
        help="This line's product_qty-weighted SHARE of the cabinet "
             "carcass volume — full carcass when this is the only "
             "density_volume line on the BoM, a fraction of it when "
             "sibling lines repeat the same sheet product (see "
             "_sb_component_share_volume_mm3 docstring). 0.0 when the "
             "volumetric source (cabinet width/height/depth) is "
             "unavailable — see _panel_volume_mm3 docstring.",
    )
    component_weight_kg = fields.Float(
        string="Weight (kg)",
        compute="_compute_component_weight",
        store=True,
        digits=(10, 2),
    )
    material_demand_qty = fields.Float(
        string="Material Demand",
        compute="_compute_material_demand_qty",
        store=True,
        digits=(12, 4),
        help="Consumption of this component per this BoM, in the material's "
             "canonical demand unit: m² for sheet/area goods (density_volume/"
             "density_area), linear m for edgebanding (linear_density), or "
             "units for hardware (per_unit/none). Continuous families reuse "
             "the geometry→volume pipeline; hardware passes product_qty "
             "through unchanged. 0.0 when geometry is genuinely absent "
             "(never fabricated). Drives the suggested purchase quantity — "
             "the native BoM product_qty is left untouched (Fork 1).",
    )
    suggested_purchase_qty = fields.Float(
        string="Suggested Order Qty",
        compute="_compute_suggested_purchase_qty",
        store=True,
        digits=(12, 2),
        help="Assist-only: CEIL(demand x (1 + waste%) / yield-per-unit) in "
             "the vendor's purchase unit. Transparent suggestion a buyer "
             "confirms - this NEVER creates or confirms a PO. 0 when demand, "
             "yield, or a vendor is missing (no fabricated suggestion).",
    )
    suggested_purchase_uom_id = fields.Many2one(
        "uom.uom", string="Suggested Order UoM",
        compute="_compute_suggested_purchase_qty", store=True,
        help="Vendor's purchase UoM (product.supplierinfo.product_uom_id) "
             "when a seller resolves, else the product's own uom_id. Odoo 19 "
             "removed product.uom_po_id (a single uom_id replaces the old "
             "sales/purchase UoM split) — verified by grep against the "
             "installed core (product/models/product_template.py, "
             "product_product.py) and against product_supplierinfo.py, "
             "which exposes product_uom_id, not product_uom.",
    )

    _SB_DEFAULT_SHEET_THICKNESS_MM = 19.05  # 3/4" — documented fallback

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

    # NOTE: product_id.product_tmpl_id.material_id is the Wave-3 product-level
    # fallback (sb_material_core) — without this dotted dep, linking a material
    # on an existing component's template never retriggers this stored compute
    # (observed live: 6 components linked by migration, all line material_id
    # stale-empty). The attribute-value path (PTAV material_id edits) still
    # doesn't retrigger — pre-existing, rare, and fixable by editing the line's
    # product; documented here for honesty.
    @api.depends("product_id", "product_id.product_tmpl_id.material_id")
    def _compute_material_id(self):
        for line in self:
            line.material_id = (
                line.product_id._resolve_material() if line.product_id else False
            )

    # ----------------------------------------------------------------
    # Task 4 (Materials Phase-2 Procurement) — the assist number.
    #
    # `product.supplierinfo` in this build's installed v19 core exposes
    # the purchase UoM as `product_uom_id`, NOT `product_uom` (the brief's
    # tentative name) — verified by grepping the running container's core
    # (`/usr/lib/python3/dist-packages/odoo/addons/product/models/
    # product_supplierinfo.py`, lines ~25-26: `product_uom_id = fields.
    # Many2one('uom.uom', ...)`).
    #
    # The brief's documented fallback, `line.product_id.uom_po_id`, does
    # NOT exist anywhere in this build: `uom_po_id` was removed from
    # product.template/product.product in this Odoo version (the old
    # separate sales/purchase UoM split was consolidated into a single
    # `uom_id`) — confirmed by grepping the entire installed core
    # (product + purchase addons) for `uom_po_id` and finding zero Python
    # hits (only stale .po translation files). Two sibling modules in
    # this same repo already document and work around the identical
    # trap: `southbrook_configurator_ux/controllers/main.py` ("product.
    # template in Odoo 19 exposes uom_id but NOT uom_po_id") and
    # `southbrook_installer/models/southbrook_damage_flag.py` ("v19
    # removed product.uom_po_id; the single product UoM is product.
    # uom_id"), both falling back to `product.uom_id`. Using the brief's
    # literal `uom_po_id` fallback would raise AttributeError on every
    # line lacking a resolved seller UoM — an unconditional crash, not a
    # graceful "no fabricated suggestion" — so this compute uses
    # `line.product_id.uom_id` instead, matching the established repo
    # precedent exactly.
    # ----------------------------------------------------------------
    @api.depends(
        "material_demand_qty", "material_id",
        "material_id.waste_pct", "material_id.family_id",
        # M-2 (final review, 2026-07-26) — retrigger when a family's
        # default_waste_pct is edited IN PLACE (not just on family
        # re-link, which "material_id.family_id" above already covers).
        # `_effective_waste_pct()` also walks `family_id.parent_id` chains
        # arbitrarily deep for the inherited-waste fallback; that
        # multi-level parent walk can't be expressed as a static dotted
        # depends (unbounded, data-dependent depth) — same documented
        # limitation as the geometry-fallback note above
        # (_compute_component_weight). This one-level dep covers the
        # common case (editing the material's own family's pct).
        "material_id.family_id.default_waste_pct",
        # I-1 (final review, 2026-07-26) — the suggestion reads
        # `product_id._select_seller().uom_yield_qty`, but only
        # `product_id` (the relation itself) was in the depends, so
        # entering the net-new vendor yield on an EXISTING supplierinfo —
        # the feature's core post-deploy data-entry step — never
        # retriggered this stored field. Add the seller fields actually
        # read: the yield itself, plus every field `_select_seller`
        # ranks sellers on (min_qty/price/date_start/date_end) and the
        # seller's UoM (feeds suggested_purchase_uom_id below).
        "product_id.seller_ids",
        "product_id.seller_ids.uom_yield_qty",
        "product_id.seller_ids.min_qty",
        "product_id.seller_ids.price",
        "product_id.seller_ids.date_start",
        "product_id.seller_ids.date_end",
        "product_id.seller_ids.product_uom_id",
        "product_id",
    )
    def _compute_suggested_purchase_qty(self):
        for line in self:
            line.suggested_purchase_qty = 0.0
            line.suggested_purchase_uom_id = False
            mat = line.material_id
            demand = line.material_demand_qty
            if not mat or demand <= 0.0:
                continue
            seller = line.product_id._select_seller() if line.product_id else False
            yield_qty = seller.uom_yield_qty if seller else 0.0
            if not seller or yield_qty <= 0.0:
                continue
            waste = mat._effective_waste_pct()
            gross = demand * (1.0 + waste / 100.0)
            # M-1 (final review, 2026-07-26) — round the ratio to 4dp before
            # ceil. Raw float division on an exact-integer boundary (e.g.
            # 5.94 / 2.97 == 2.0 mathematically) can land a hair above the
            # integer (2.0000000000000004) due to binary FP representation,
            # and `math.ceil` on that over-orders by a whole purchase unit.
            # float_round to 4dp is well below any real yield/demand
            # precision this module carries, so it never masks a genuine
            # fractional ratio (e.g. 1.885 still rounds to 1.885 -> ceil 2).
            ratio = float_round(gross / yield_qty, precision_digits=4)
            line.suggested_purchase_qty = float(math.ceil(ratio))
            line.suggested_purchase_uom_id = (
                seller.product_uom_id or line.product_id.uom_id
            ).id

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

    def _sb_resolve_geo(self):
        """Resolve the cabinet geometry dict for this line: per-line override
        (all three sb_line_* set) merged over the cabinet variant geometry,
        else the variant geometry, else {} (honesty). Single source of truth
        shared by _panel_volume_mm3 and _compute_material_demand_qty.

        Extracted verbatim (Phase-2 Task 3) from the geometry-resolution
        block that used to live inline in `_panel_volume_mm3` — a pure
        refactor, not a behavior change; `_panel_volume_mm3` now calls this
        method instead of resolving geo itself.
        """
        self.ensure_one()
        cab = self.bom_id.product_id or self.bom_id.product_tmpl_id.product_variant_id
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
        if self.sb_line_width_mm and self.sb_line_height_mm and self.sb_line_depth_mm:
            line_geo = {
                **base_geo,
                "width_mm": self.sb_line_width_mm,
                "height_mm": self.sb_line_height_mm,
                "depth_mm": self.sb_line_depth_mm,
            }
        return line_geo or base_geo

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

        geo = line._sb_resolve_geo()
        if not geo:
            cab = line.bom_id.product_id or line.bom_id.product_tmpl_id.product_variant_id
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

    def _sb_density_volume_sibling_total_qty(self, line):
        """Sum of `product_qty` over every line on `line.bom_id` that also
        resolves to a `density_volume` material — `line` itself included.

        Uses each sibling's raw, un-exploded `product_qty` (not an
        explode()-multiplied quantity) deliberately: the multiplier a
        phantom/nested BoM applies is uniform across all sibling lines of
        the SAME `bom_id`, so it cancels out of the qty-weighted RATIO
        this total feeds into (`_sb_component_share_volume_mm3` below) —
        using the raw column keeps this helper a pure, cheap ORM read
        with no dependency on the caller's explode() context.

        Falls back to `line.product_qty or 1.0` in the (pathological)
        case where the sibling set sums to 0, to avoid a division by
        zero while still never fabricating a weight for a genuinely
        zero-qty line.
        """
        siblings = line.bom_id.bom_line_ids.filtered(
            lambda l: l.material_id and l.material_id.weight_source == "density_volume"
        )
        total_qty = sum(siblings.mapped("product_qty"))
        return total_qty or line.product_qty or 1.0

    def _sb_component_share_volume_mm3(self, line, _dims_cache=None):
        """Estimation-grade weight attribution (live defect fix,
        2026-07-26) — this line's product_qty-weighted SHARE of the
        carcass volume `_panel_volume_mm3` resolves for it.

        A configurator-built BoM has exactly one density_volume sheet
        line per cabinet, so `_panel_volume_mm3`'s full-carcass answer
        was always correct there. Live hand-built/imported BoMs instead
        repeat the same sheet product across several per-panel lines
        (e.g. one line per side/top/bottom/shelf), and giving EACH of
        those lines the whole carcass over-counted the BoM's total
        material weight by roughly the sibling count. Determining which
        physical panel belongs to which line is Phase-2 cutlist
        territory (out of scope here); the invariant THIS fix
        guarantees is that the BoM's total counts the carcass exactly
        once, split proportionally by each sibling's own `product_qty`:

            line_share = carcass_vol * (line.product_qty / total_qty)

        where `total_qty` is the sum of `product_qty` over every
        density_volume-resolving sibling line on the same `bom_id`
        (`_sb_density_volume_sibling_total_qty`, itself included).

        Implementation note: `_weight_for_qty` (the LOCKED conversion's
        caller) already multiplies whatever volume it's given by
        `line.product_qty` — so the PER-UNIT volume this method must
        return is `carcass_vol / total_qty` (the `line.product_qty`
        factor in `line_share` above is supplied by that existing
        multiplication, not duplicated here). This also correctly
        collapses to `carcass_vol / line.product_qty` for a lone
        sibling — which, multiplied back by `line.product_qty` in
        `_weight_for_qty`, reproduces `carcass_vol` exactly: a single
        density_volume line's stored weight is therefore BYTE-IDENTICAL
        to the pre-fix behavior (100% share, never divided in practice
        for the qty=1 lines every existing single-line test uses).

        A line carrying its own `sb_line_*` geometry override still
        computes its OWN carcass volume from those override dims (via
        `_panel_volume_mm3`'s existing merge semantics) — this method
        then divides THAT override-based volume by the same
        sibling-qty total, rather than special-casing overridden lines
        out of the shared attribution.

        Honesty contract unchanged: 0.0 (never fabricated) whenever
        `_panel_volume_mm3` itself returns 0.0 (no geometry).
        """
        carcass_vol = self._panel_volume_mm3(line, _dims_cache=_dims_cache)
        if not carcass_vol:
            return 0.0
        total_qty = self._sb_density_volume_sibling_total_qty(line)
        return carcass_vol / total_qty

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
        # Sibling weight-attribution fix (live defect, 2026-07-26) — this
        # line's share depends on every OTHER density_volume-resolving
        # line on the same bom_id, not just its own fields: adding or
        # editing a sibling's qty/material must retrigger this line's
        # stored share too, or it goes stale exactly like the defect
        # this fix closes.
        "bom_id.bom_line_ids.product_qty",
        "bom_id.bom_line_ids.material_id",
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
                self._sb_component_share_volume_mm3(line, _dims_cache=dims_cache)
                if m.weight_source == "density_volume"
                else 0.0
            )
            line.component_volume_mm3 = vol
            line.component_weight_kg = self._weight_for_qty(m, vol, line.product_qty)

    @api.depends(
        "product_id", "product_qty", "material_id",
        "material_id.weight_source", "material_id.thickness_mm",
        "sb_line_width_mm", "sb_line_height_mm", "sb_line_depth_mm",
        "bom_id.product_id.sb_width_mm",
        "bom_id.product_id.sb_height_mm",
        "bom_id.product_id.sb_depth_mm",
        # T3 review fix: edge_banding_length_mm (linear_density branch)
        # varies with finished_sides; and the density_volume/area branch's
        # _sb_component_share_volume_mm3 is sibling-qty-weighted, so it must
        # recompute when a sibling line's qty/material changes — mirror the
        # deps _compute_component_weight already carries for the same share.
        "bom_id.product_id.sb_finished_sides",
        "bom_id.bom_line_ids.product_qty",
        "bom_id.bom_line_ids.material_id",
    )
    def _compute_material_demand_qty(self):
        """Consumption of this component per this BoM, in the material's
        canonical demand unit (Phase-2 Task 3 — see field help for the full
        rule). Computation rule (exact, per weight_source):

        - density_volume / density_area: area_m2 = (this line's product_qty-
          weighted SHARE of the carcass volume, `_sb_component_share_volume_
          mm3` — the same sibling-attribution-aware PER-UNIT volume
          `component_volume_mm3` already uses) * line.product_qty /
          effective_thickness_mm / 1_000_000.0 — the `* line.product_qty`
          mirrors the weight path (`_weight_for_qty`) and the linear branch
          below, both of which multiply their per-unit quantity through;
          the share helper's contract is explicitly PER-UNIT (see its
          docstring), so the caller must apply product_qty (C-1 fix, final
          review 2026-07-26 — previously omitted here, silently
          under-counting demand on any density line with product_qty != 1).
          effective_thickness_mm is material.thickness_mm when > 0, else the
          3/4" cut-constant fallback (`_SB_DEFAULT_SHEET_THICKNESS_MM`,
          19.05 — same cut-constant family `_panel_volume_mm3` already
          uses). 0.0 when the share volume is 0.0 (honesty — geometry
          genuinely absent).

          M-3 (doc only, final review 2026-07-26): `density_area` lines are
          NOT members of the `density_volume`-only sibling set
          (`_sb_density_volume_sibling_total_qty` filters on
          `weight_source == "density_volume"`), so a `density_area` line's
          demand is always standalone — its `total_qty` falls back to its
          own `product_qty` rather than being shared with any
          `density_volume` siblings on the same BoM. Accepted as-is:
          `density_area` is rare and already produces 0.0 weight in
          `_compute_component_weight` today (see `_weight_for_qty`'s
          density_area branch); the filter is deliberately NOT changed here
          to avoid altering the locked `density_volume` attribution
          invariant this review is closing out.
        - linear_density: resolve the cabinet geometry exactly as
          `_panel_volume_mm3` does (`_sb_resolve_geo`), then length_m =
          `_compute_panel_dimensions(**geo)["edge_banding_length_mm"] /
          1000.0 * line.product_qty`. 0.0 when geo is {} (honesty).
        - per_unit / none / no material_id: material_demand_qty =
          line.product_qty (straight pass-through — the native count model
          is already correct for hardware).

        M-4 (perf, final review 2026-07-26): a single `dims_cache` dict is
        threaded through this whole compute pass (mirroring
        `_compute_component_weight`'s `dims_cache`) so lines sharing a
        `bom_id`/geometry hit the cache instead of re-solving
        `_compute_panel_dimensions` once per line — for both the density
        share wrapper AND the linear-branch's direct call. Behavior is
        byte-identical: a cache hit returns the exact same `dims` a fresh
        call would produce (see `_panel_volume_mm3`'s cache docstring).
        """
        Bom = self.env["mrp.bom"]
        has_geo = hasattr(Bom, "_compute_panel_dimensions")
        dims_cache = {}
        for line in self:
            mat = line.material_id
            src = mat.weight_source if mat else "none"
            if src in ("density_volume", "density_area"):
                vol = line._sb_component_share_volume_mm3(line, _dims_cache=dims_cache)
                if not vol:
                    line.material_demand_qty = 0.0
                    continue
                th = mat.thickness_mm if mat.thickness_mm > 0 else \
                    line._SB_DEFAULT_SHEET_THICKNESS_MM
                # C-1 fix (final review, 2026-07-26): `vol` is the PER-UNIT
                # share (see docstring above) — multiply by product_qty,
                # exactly like the weight path and the linear branch below.
                line.material_demand_qty = vol * line.product_qty / th / 1_000_000.0
            elif src == "linear_density":
                geo = line._sb_resolve_geo() if has_geo else {}
                if not geo:
                    line.material_demand_qty = 0.0
                    continue
                cache_key = tuple(sorted(geo.items()))
                dims = dims_cache.get(cache_key)
                if dims is None:
                    dims = Bom._compute_panel_dimensions(**geo)
                    dims_cache[cache_key] = dims
                length_mm = dims.get("edge_banding_length_mm") or 0
                line.material_demand_qty = length_mm / 1000.0 * line.product_qty
            else:
                # per_unit / none / no material: native count model is correct
                line.material_demand_qty = line.product_qty


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
                    line._sb_component_share_volume_mm3(line, _dims_cache=dims_cache)
                    if m.weight_source == "density_volume"
                    else 0.0
                )
                total += line._weight_for_qty(m, vol, qty)
            bom.material_weight_total = float_round(
                total, precision_digits=2, rounding_method="HALF-UP"
            )
