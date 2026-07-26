# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.5.0 — Hygiene A2: relink the 2 live legacy sheet-good
components to their new thickness-specific `southbrook.kitchen.
material` (added in `data/material_seed_data.xml` — `mat_mel_58` /
`mat_hardboard_14`), off the GENERIC `melamine`/`mdf` materials they
currently resolve to.

Background (see the seed-data comment for the full rationale): the
generic `melamine`/`mdf` materials carry no `thickness_mm` (used at
multiple thicknesses across the catalog) so `RM-MELAMINE_WHITE_5_8`
(5/8") and `RM-HARDBOARD_1_4` (1/4") both fall back to the 3/4"=
19.05mm cut constant in `material_demand_qty`'s area calc, under-
stating the true panel area for these thinner sheets. Setting
thickness on the shared generic material would be WRONG (it would
mis-apply to every OTHER product still correctly resolving to the
generic 3/4" default) -- the correct fix is dedicated thickness-
specific materials + a targeted relink, exactly mirroring the
19.0.1.3.0 Repair-Wave-3 migration's `_COMPONENT_MATERIAL_MAP` /
`_link_component_materials` / `_recompute_dependent_bom_lines`
idiom (this file is a straight copy of that shape, scoped to these
2 products).

CONFIRMED mapping (per the hygiene A2 brief):
    RM-MELAMINE_WHITE_5_8  -> sb_material_core.mat_mel_58 (15.875mm)
    RM-HARDBOARD_1_4       -> sb_material_core.mat_hardboard_14 (6.35mm)

Idempotent + non-destructive:
  - Only relinks a product.template whose `material_id` is CURRENTLY
    UNSET, or CURRENTLY POINTING AT THE GENERIC material it is being
    upgraded away from (code 'melamine' / 'mdf') -- a shop that has
    since hand-linked (or corrected) a component's material to
    something else entirely is never overwritten.
  - `env.ref(..., raise_if_not_found=False)` / `search(...)` both skip
    gracefully when a product or the new material is absent (e.g. a
    fresh install with no live-created components yet) -- this
    migration is a LIVE-DB repair, not a fresh-install requirement.

After relinking, `mrp.bom.line.material_id` (compute+store) and the
`component_weight_kg` / `component_volume_mm3` / `material_demand_qty`
fields that read it are stale for every existing line whose
`product_id` is one of these 2 components, for the exact same reason
documented in the 19.0.1.3.0 migration's docstring: `product_id`
itself didn't change, only its template's `material_id` fallback,
invisible to the ORM dependency graph through `_resolve_material()`'s
Python-level fallback. Force + flush `material_id` first, then the
weight/volume/demand fields that read it.

Soft-guarded: `sb_material_mrp` is not a manifest dependency of
`sb_material_core` (it is the other way around), so `mrp.bom.line`
may not carry `material_id` / `material_demand_qty` at all when this
runs -- skip the recompute step silently in that case; the
product-level relink itself is unaffected.
"""

import logging

_logger = logging.getLogger(__name__)

# default_code -> (new material xml_id, generic material `code` being
# relinked AWAY FROM -- used only to decide whether an already-set
# material_id is safe to overwrite).
_COMPONENT_MATERIAL_MAP = {
    "RM-MELAMINE_WHITE_5_8": ("sb_material_core.mat_mel_58", "melamine"),
    "RM-HARDBOARD_1_4": ("sb_material_core.mat_hardboard_14", "mdf"),
}


def _relink_component_materials(env):
    """Hygiene A2: relink the 2 live component products' `material_id`
    fallback from the generic melamine/mdf material to the new
    thickness-specific one. Returns the `product.product` recordset
    actually updated (informational + used to scope the dependent-
    BoM-line recompute).
    """
    Product = env["product.product"]
    updated_products = Product.browse()

    for default_code, (new_ref, generic_code) in _COMPONENT_MATERIAL_MAP.items():
        product = Product.search([("default_code", "=", default_code)], limit=1)
        if not product:
            _logger.info(
                "sb_material_core 19.0.1.5.0 migration: no product with "
                "default_code=%s -- skipping (fresh install or not yet "
                "created).", default_code,
            )
            continue

        new_material = env.ref(new_ref, raise_if_not_found=False)
        if not new_material:
            _logger.info(
                "sb_material_core 19.0.1.5.0 migration: material %s not "
                "found for default_code=%s -- skipping.", new_ref, default_code,
            )
            continue

        tmpl = product.product_tmpl_id
        current = tmpl.material_id
        if current and current.code != generic_code:
            _logger.info(
                "sb_material_core 19.0.1.5.0 migration: %s already has "
                "material_id=%s (not the generic '%s') -- leaving "
                "untouched.", default_code, current.display_name, generic_code,
            )
            continue

        tmpl.write({"material_id": new_material.id})
        updated_products |= product
        _logger.info(
            "sb_material_core 19.0.1.5.0 migration: relinked %s -> %s.",
            default_code, new_material.display_name,
        )

    return updated_products


def _recompute_dependent_bom_lines(env, products):
    """Mirror the 19.0.1.3.0 migration's `_recompute_dependent_bom_
    lines` exactly: force the now-stale `mrp.bom.line.material_id`
    (then the weight/volume/demand fields that read it) to recompute
    and flush for every line whose component is one of the just-
    relinked products.
    """
    BomLine = env["mrp.bom.line"]
    if "material_id" not in BomLine._fields:
        _logger.info(
            "sb_material_core 19.0.1.5.0 migration: mrp.bom.line has no "
            "material_id field (sb_material_mrp not installed) -- "
            "skipping dependent BoM-line recompute.",
        )
        return 0
    if not products:
        return 0

    lines = BomLine.sudo().search([("product_id", "in", products.ids)])
    if not lines:
        return 0

    # Step 1: material_id is the newly-stale field. Force + flush it first.
    material_field = BomLine._fields["material_id"]
    env.add_to_compute(material_field, lines)
    material_field.recompute(lines)
    lines.flush_recordset(["material_id"])

    # Step 2: component_weight_kg / component_volume_mm3 share one compute
    # method and read material_id -- force + flush now that it is fresh.
    if "component_weight_kg" in BomLine._fields:
        weight_field = BomLine._fields["component_weight_kg"]
        volume_field = BomLine._fields["component_volume_mm3"]
        env.add_to_compute(weight_field, lines)
        env.add_to_compute(volume_field, lines)
        weight_field.recompute(lines)
        lines.flush_recordset(["component_weight_kg", "component_volume_mm3"])

    # Step 3 (A2-specific): material_demand_qty (Phase-2 Task 3) also
    # reads material_id (via material_id.thickness_mm) and is not
    # covered by the weight/volume compute method above -- force +
    # flush it separately so the area under-statement this migration
    # exists to fix is actually corrected on the live BoM lines.
    if "material_demand_qty" in BomLine._fields:
        demand_field = BomLine._fields["material_demand_qty"]
        env.add_to_compute(demand_field, lines)
        demand_field.recompute(lines)
        lines.flush_recordset(["material_demand_qty"])

    return len(lines)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "sb_material_core 19.0.1.5.0 migration: relinking the 2 live "
        "legacy sheet-good components to their thickness-specific "
        "material (from %s)", version,
    )
    updated_products = _relink_component_materials(env)
    _logger.info(
        "sb_material_core 19.0.1.5.0 migration: %s product(s) relinked.",
        len(updated_products),
    )
    n_lines = _recompute_dependent_bom_lines(env, updated_products)
    _logger.info(
        "sb_material_core 19.0.1.5.0 migration: %s mrp.bom.line(s) "
        "recomputed.", n_lines,
    )
