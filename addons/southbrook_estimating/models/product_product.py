# SPDX-License-Identifier: LGPL-3.0-only
"""T2 — Door-area m² computed on the configured variant.

Door area is the load-bearing input for paint / lacquer / spray-finish
pricelist rollups. Today Southbrook prices doors per-piece; Prodboard's
catalogue surfaces a 0.423 m² figure on every cabinet detail panel
because the finish cost actually scales with surface area, not piece
count. Adding the metric lets a future pricelist rule key off it.

Computed from:
  - Width attribute pick (mm)
  - Door Count attribute pick (or derived from family default)
  - cabinet-class default height (720mm Base, 1970mm Tall, 720mm Wall —
    overridable via an explicit Height attribute pick)
  - DOOR_REVEAL = 3mm gap per door edge (from shared.southbrook_dims)

Returns 0.0 when the variant carries no configurator picks (templates
without attribute lines). Stored so reporting + pricelist rules can
domain on it.
"""
from odoo import api, fields, models


# Mirror of shared.southbrook_dims.DOOR_REVEAL — kept local so this
# module doesn't grow a runtime dependency on the shared package just
# for one constant. If the canonical reveal changes, update both.
_DOOR_REVEAL_MM = 3.0


# Class-default heights when the variant doesn't expose Height.
_DEFAULT_HEIGHT_BY_CATEGORY = {
    "Base":   720.0,
    "Drawer": 720.0,
    "Wall":   720.0,
    "Tall":   1970.0,
    "Vanity": 720.0,
}


class ProductProduct(models.Model):
    _inherit = "product.product"

    x_door_area_m2 = fields.Float(
        string="Door Area (m²)",
        compute="_compute_x_door_area_m2",
        store=True,
        digits=(8, 4),
        help="Sum of all door-face areas for this variant in m². "
             "Computed from the configurator's Width pick × "
             "(picked or class-default Height) × picked Door Count, "
             "minus a 3mm reveal per door edge. Used by paint / "
             "lacquer / spray-finish pricelist rules that scale by "
             "surface area rather than per-piece.",
    )

    # Task A1 — Materials geometry-writeback fields
    sb_width_mm = fields.Integer(
        string="Cabinet Width (mm)",
        help="Configured outer width; set at variant creation for the Materials weight calc.",
    )
    sb_height_mm = fields.Integer(
        string="Cabinet Height (mm)",
    )
    sb_depth_mm = fields.Integer(
        string="Cabinet Depth (mm)",
    )
    sb_panel_family = fields.Char(
        string="Panel Family",
        default="base",
    )
    sb_door_count = fields.Integer(
        string="Door Count",
        default=1,
    )
    sb_drawer_count = fields.Integer(
        string="Drawer Count",
        default=0,
    )
    sb_finished_sides = fields.Char(
        string="Finished Sides",
        default="none",
    )

    @api.depends("product_template_attribute_value_ids",
                 "product_template_attribute_value_ids.product_attribute_value_id",
                 "product_tmpl_id.southbrook_category")
    def _compute_x_door_area_m2(self):
        for variant in self:
            try:
                variant.x_door_area_m2 = variant._t2_door_area_m2()
            except Exception:  # noqa: BLE001
                # Never let a malformed pick break the recompute pass —
                # the field is informational, not load-bearing.
                variant.x_door_area_m2 = 0.0

    def _t2_door_area_m2(self):
        self.ensure_one()
        picks = self.product_template_attribute_value_ids
        if not picks:
            return 0.0

        # Index picks by attribute name (case-insensitive, stripped).
        by_attr = {}
        for ptav in picks:
            attr_name = (ptav.attribute_id.name or "").strip().lower()
            value_name = (ptav.product_attribute_value_id.name or "").strip()
            by_attr[attr_name] = value_name

        width_mm = self._t2_parse_dim_mm(by_attr.get("width"))
        height_mm = self._t2_parse_dim_mm(by_attr.get("height"))
        if not height_mm:
            # Fall back to the cabinet-class default per
            # product.template.southbrook_category.
            cat = (self.product_tmpl_id.southbrook_category or "").strip()
            height_mm = _DEFAULT_HEIGHT_BY_CATEGORY.get(cat, 720.0)

        if not width_mm:
            return 0.0

        door_count = self._t2_door_count(by_attr)
        if not door_count:
            return 0.0

        # Geometric door dimensions per shared.southbrook_dims.door():
        #   1 door : (height - 2*reveal) × (width - 2*reveal)
        #   2 doors: (height - 2*reveal) × ((width - 3*reveal)/2) × 2
        door_height_mm = height_mm - 2 * _DOOR_REVEAL_MM
        if door_count == 1:
            door_width_mm = width_mm - 2 * _DOOR_REVEAL_MM
        elif door_count == 2:
            door_width_mm = (width_mm - 3 * _DOOR_REVEAL_MM) / 2.0
        else:
            # 3+ doors aren't supported by the canonical door() function;
            # estimate as (width - (n+1)*reveal) / n per door.
            door_width_mm = (
                width_mm - (door_count + 1) * _DOOR_REVEAL_MM
            ) / float(door_count)
        if door_width_mm <= 0 or door_height_mm <= 0:
            return 0.0
        total_mm2 = door_count * door_width_mm * door_height_mm
        return total_mm2 / 1_000_000.0

    @staticmethod
    def _t2_parse_dim_mm(raw):
        """'24 in' / '600mm' / '600' -> millimetres float. Returns 0 on
        unrecognised input."""
        if not raw:
            return 0.0
        s = str(raw).strip().lower().replace(",", "")
        if "(" in s:
            s = s.split("(", 1)[0].strip()
        is_inches = ("in" in s) or ('"' in s)
        s = s.replace("mm", "").replace("in", "").replace('"', "").replace(" ", "")
        try:
            n = float(s)
        except (TypeError, ValueError):
            return 0.0
        return n * 25.4 if is_inches else n

    def _t2_door_count(self, by_attr):
        # Explicit pick wins — but attr_door_count is hidden per Q22(a)
        # in the canonical seed, so real cabinets rarely carry one.
        explicit = by_attr.get("door count") or by_attr.get("doors")
        if explicit:
            try:
                return int(str(explicit).split()[0])
            except (TypeError, ValueError):
                pass
        # Drawer banks have zero door faces (drawer fronts aren't doors
        # for finish-area purposes — they're priced separately).
        construction = (by_attr.get("drawer construction") or "").lower()
        if construction and "drawer" in construction:
            return 0
        # Width -> door count derivation, matching the documented rule in
        # Southbrook_Excel_to_Odoo_Mapping §3.4 (and the P1 inference at
        # sb_production_package._infer_door_count). 9-21" (~228-533mm)
        # = 1 door; 24-36" (~609-914mm) = 2 doors. Without this fallback
        # the door-area metric silently halves on every wall_2dr /
        # base_2dr template because Q22(a) hides the explicit Door Count
        # attribute on most catalogue cabinets.
        width_mm = self._t2_parse_dim_mm(by_attr.get("width"))
        if 540.0 < width_mm <= 920.0:
            return 2
        return 1

    def _sb_backfill_geometry(self):
        """Task A3 — backfill sb_width_mm/height_mm/depth_mm on variants
        that existed BEFORE Task A2's write-at-config-time hook, or that
        were otherwise created outside `product.config.session.get_variant_vals`
        (e.g. direct `create()`, imports, demo data).

        Idempotent: only ever touches variants where all three of
        sb_width_mm / sb_height_mm / sb_depth_mm are currently 0. A
        variant that already carries real (or previously-backfilled, or
        manually-corrected) dimensions is never overwritten — running
        this on every `-u` is always safe.

        Resolution per candidate variant, keyed by `default_code`:
          1. Look up `default_code` in `_SKU_DEFAULTS` (the SAME table
             A2 uses — sourced from `product.config.session`, never
             duplicated here) for family/door_count/drawer_count and
             the SKU's baked H/D/W.
          2. If the variant carries an `attr_width` attribute-value pick
             with a `value_mm`, that ACTUAL configured width overrides
             the SKU table's baked width (it reflects what the variant
             really is, not just its template's default).
          3. A variant resolves only when width_mm, height_mm AND
             depth_mm all end up non-zero. Height/depth have no source
             other than the SKU table, so a variant with an unknown/
             absent default_code (no SKU-table hit) is left untouched
             at 0/0/0 — writing a guessed height or depth would be
             dishonest. This also covers "no default_code and no
             attr_width": nothing resolves, nothing is written.

        Returns the count of variants updated (informational; callers
        don't need to act on it).
        """
        sku_defaults = self.env["product.config.session"]._SKU_DEFAULTS
        attr_width = self.env.ref(
            "southbrook_estimating.attr_width", raise_if_not_found=False,
        )

        candidates = self.search([
            ("sb_width_mm", "=", 0),
            ("sb_height_mm", "=", 0),
            ("sb_depth_mm", "=", 0),
        ])
        updated = 0
        updated_variants = self.browse()
        for variant in candidates:
            sku = variant.default_code or ""
            sku_row = sku_defaults.get(sku)
            if not sku_row:
                # No H/D signal available at all — leave honestly at 0.
                continue
            family, door_count, drawer_count, width_mm, height_mm, depth_mm = (
                sku_row
            )

            if attr_width:
                for ptav in variant.product_template_attribute_value_ids:
                    pav = ptav.product_attribute_value_id
                    if pav.attribute_id == attr_width and pav.value_mm:
                        width_mm = pav.value_mm
                        break

            variant.write({
                "sb_width_mm": width_mm,
                "sb_height_mm": height_mm,
                "sb_depth_mm": depth_mm,
                "sb_panel_family": family,
                "sb_door_count": door_count,
                "sb_drawer_count": drawer_count,
            })
            updated += 1
            updated_variants |= variant

        if updated_variants:
            self._sb_recompute_dependent_bom_weights(updated_variants)
        return updated

    def _sb_recompute_dependent_bom_weights(self, variants):
        """Finding I-2 fix (final review, 2026-07-24).

        `sb_material_mrp.mrp.bom.line.component_weight_kg` /
        `component_volume_mm3` are `store=True` but their `@api.depends`
        cannot fully reach through to a cabinet variant's geometry (see
        that field's depends-list comment) — so when THIS method backfills
        geometry onto a variant that already has BoM lines pointing at it
        (`bom_id.product_id`), those lines' stored weight/volume would
        otherwise stay frozen at their prior (usually 0.00) value until
        something unrelated happened to touch them. That's display-only
        staleness (the unstored `mrp.bom.material_weight_total` headline
        is always fresh), but real: the bom.line view would show a wrong
        number right after this backfill runs.

        Soft-guarded: `sb_material_mrp` is not a hard manifest dependency
        of `southbrook_estimating` (it's the other way around — see that
        module's `mrp_bom.py` docstring), so `mrp.bom.line` may not carry
        these fields at all when this runs; skip silently in that case.

        Mechanism: mark the two co-computed fields "to compute" for every
        affected line (`env.add_to_compute`), then process that pending
        computation immediately via `Field.recompute()` (the same call
        Odoo's own flush cycle would eventually make) and flush the
        result to the database — rather than leaving it queued for
        whatever unrelated flush happens to come next.
        """
        BomLine = self.env["mrp.bom.line"]
        if "component_weight_kg" not in BomLine._fields:
            return
        # FIX-B (repair wave 1, finding #2) — this used to search only
        # `bom_id.product_id in variants`, which misses template-level
        # BoMs (`product_id` unset). 22/23 LIVE BoMs are template-level;
        # their read path (`_panel_volume_mm3`) falls back to
        # `bom_id.product_tmpl_id.product_variant_id` (the template's
        # first variant) when `product_id` is False. Backfilling
        # geometry onto that fallback variant must still recompute those
        # lines, or the stored weight stays frozen at 0.00 forever.
        #
        # `product_tmpl_id.product_variant_id` is itself a non-stored
        # compute (`product.template._compute_product_variant_id`,
        # Odoo 19 core) — it CANNOT appear in an ORM search domain
        # (`ValueError: ... is not stored`). So this is a two-phase
        # match: (1) a broad SQL search on the real, stored
        # `product_variant_ids` One2many to find every candidate
        # template-level BoM that has ANY backfilled variant on its
        # template, then (2) a precise Python-side filter down to only
        # the lines whose ACTUAL read-path fallback
        # (`product_variant_id`, i.e. variant_ids[:1]) is one of the
        # backfilled variants — so a multi-variant template that
        # happened to backfill a non-first variant is correctly left
        # alone (that variant is never read by `_panel_volume_mm3`).
        candidate_lines = BomLine.sudo().search([
            "|",
            ("bom_id.product_id", "in", variants.ids),
            "&",
            ("bom_id.product_id", "=", False),
            ("bom_id.product_tmpl_id.product_variant_ids", "in", variants.ids),
        ])
        if not candidate_lines:
            return
        variant_id_set = set(variants.ids)
        lines = candidate_lines.filtered(
            lambda l: (
                l.bom_id.product_id.id in variant_id_set
                if l.bom_id.product_id
                else l.bom_id.product_tmpl_id.product_variant_id.id in variant_id_set
            )
        )
        if not lines:
            return
        weight_field = BomLine._fields["component_weight_kg"]
        volume_field = BomLine._fields["component_volume_mm3"]
        self.env.add_to_compute(weight_field, lines)
        self.env.add_to_compute(volume_field, lines)
        weight_field.recompute(lines)
        lines.flush_recordset(["component_weight_kg", "component_volume_mm3"])

    def _sb_geometry_inputs(self):
        """Task A1 — Return geometry inputs dict for Materials calc.

        Returns a dict with keys {width_mm, height_mm, depth_mm, family,
        door_count, drawer_count, finished_sides} when all three dimensions
        are non-zero; returns {} otherwise.
        """
        self.ensure_one()
        if not (self.sb_width_mm and self.sb_height_mm and self.sb_depth_mm):
            return {}
        return {
            "width_mm": self.sb_width_mm,
            "height_mm": self.sb_height_mm,
            "depth_mm": self.sb_depth_mm,
            "family": self.sb_panel_family or "base",
            "door_count": self.sb_door_count,
            "drawer_count": self.sb_drawer_count,
            "finished_sides": self.sb_finished_sides or "none",
        }
