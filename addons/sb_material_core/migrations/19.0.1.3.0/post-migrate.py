# SPDX-License-Identifier: LGPL-3.0-only
"""
19.0.1.3.0 — Repair Wave 3: link the 6 live BoM sheet-good component
products to a `southbrook.kitchen.material` via the new
`product.template.material_id` fallback field (see
`models/product_template.py` + `_resolve_material()`'s Wave-3 fallback
branch, `models/product_attribute_value.py`).

These 6 components are plain products (no attributes at all), so before
this wave `_resolve_material()` returned an empty recordset for every
one of them -> `mrp.bom.line.material_id` -> `component_weight_kg` ->
`mrp.bom.material_weight_total` all multiplied to 0.00 on the LIVE DB,
even though geometry (Repair Wave 1) and family/density (Repair Wave 2)
are both live.

CONFIRMED mapping (default_code -> material), from the repair-wave-3
brief:
    SBK-SHEET-MB34-WW      -> ref sb_material_core.mat_melamine_34
    SBK-SHEET-BPY12        -> ref sb_material_core.mat_ply_12
    SBK-SHEET-BPY14        -> ref sb_material_core.mat_ply_14_back
    RM-PLY_3_4             -> ref sb_material_core.mat_ply_34
    RM-MELAMINE_WHITE_5_8  -> search code='melamine' (legacy pre-existing
                              record from southbrook_mrp_kitchen_workcenters,
                              family-backfilled by Repair Wave 2)
    RM-HARDBOARD_1_4       -> search code='mdf' (legacy pre-existing
                              record; estimation-grade approximation —
                              hardboard has no dedicated material record
                              yet, so it borrows the mdf/fiberboard family
                              default density per the brief)

Idempotent + non-destructive:
  - Only ever writes `material_id` on a product.template whose
    `material_id` is CURRENTLY UNSET (`False`) — a shop that has since
    hand-linked (or corrected) a component's material via the new form
    field is never overwritten.
  - `env.ref(..., raise_if_not_found=False)` / `search(...)` both skip
    gracefully when a product or material is absent (e.g. a fresh
    install with no live-created components, or a DB where Repair
    Wave 2's family backfill hasn't run) — this migration is a LIVE-DB
    repair, not a fresh-install requirement (fresh installs are honestly
    "no material" until someone links one by hand or a future seed
    covers it).

After linking, `mrp.bom.line.material_id` (compute+store, `@api.depends
("product_id")`) is stale for every existing line whose `product_id` is
one of these components — `product_id` itself didn't change, only its
template's new `material_id` fallback, which the depends-list has no
way to express (a `product.template` field changing doesn't invalidate
a `product.product`-keyed compute the ORM dependency graph can't see
through `_resolve_material()`'s Python-level fallback). Mirrors
`southbrook_estimating.product.product._sb_recompute_dependent_bom_
weights()`'s mechanism exactly (see that method's docstring for the
underlying `env.add_to_compute` / `Field.recompute` / `flush_recordset`
pattern): force `material_id` to recompute and flush FIRST (it's the
newly-stale field), then force `component_weight_kg` /
`component_volume_mm3` to recompute and flush (they read the now-fresh
`material_id`, but were themselves never marked dirty since it's a
Python-level fallback the ORM dependency graph doesn't reach).

Soft-guarded: `sb_material_mrp` is not a manifest dependency of
`sb_material_core` (it's the other way around), so `mrp.bom.line` may
not carry `material_id` at all when this runs (e.g. `sb_material_core`
upgraded alone) — skip the recompute step silently in that case; the
product-level link itself is unaffected.
"""

import logging

_logger = logging.getLogger(__name__)

# default_code -> ("ref", xml_id) | ("code", material code)
_COMPONENT_MATERIAL_MAP = {
    "SBK-SHEET-MB34-WW": ("ref", "sb_material_core.mat_melamine_34"),
    "SBK-SHEET-BPY12": ("ref", "sb_material_core.mat_ply_12"),
    "SBK-SHEET-BPY14": ("ref", "sb_material_core.mat_ply_14_back"),
    "RM-PLY_3_4": ("ref", "sb_material_core.mat_ply_34"),
    "RM-MELAMINE_WHITE_5_8": ("code", "melamine"),
    "RM-HARDBOARD_1_4": ("code", "mdf"),
}


def _link_component_materials(env):
    """Repair Wave 3: link the 6 live component products' `material_id`
    fallback. Returns the `product.product` recordset actually updated
    (informational + used to scope the dependent-BoM-line recompute).
    """
    Product = env["product.product"]
    Material = env["southbrook.kitchen.material"]
    updated_products = Product.browse()

    for default_code, (kind, ref) in _COMPONENT_MATERIAL_MAP.items():
        product = Product.search([("default_code", "=", default_code)], limit=1)
        if not product:
            _logger.info(
                "sb_material_core 19.0.1.3.0 migration: no product with "
                "default_code=%s — skipping (fresh install or not yet "
                "created).", default_code,
            )
            continue

        if kind == "ref":
            material = env.ref(ref, raise_if_not_found=False)
        else:
            material = Material.search([("code", "=", ref)], limit=1)
        if not material:
            _logger.info(
                "sb_material_core 19.0.1.3.0 migration: material %s not "
                "found for default_code=%s — skipping.", ref, default_code,
            )
            continue

        tmpl = product.product_tmpl_id
        if tmpl.material_id:
            _logger.info(
                "sb_material_core 19.0.1.3.0 migration: %s already has "
                "material_id=%s set — leaving untouched.",
                default_code, tmpl.material_id.display_name,
            )
            continue

        tmpl.write({"material_id": material.id})
        updated_products |= product
        _logger.info(
            "sb_material_core 19.0.1.3.0 migration: linked %s -> %s.",
            default_code, material.display_name,
        )

    return updated_products


def _recompute_dependent_bom_lines(env, products):
    """Mirror `southbrook_estimating.product.product._sb_recompute_
    dependent_bom_weights()`'s mechanism (see module docstring): force
    the now-stale `mrp.bom.line.material_id` (then the weight/volume
    fields that read it) to recompute and flush for every line whose
    component is one of the just-linked products.
    """
    BomLine = env["mrp.bom.line"]
    if "material_id" not in BomLine._fields:
        _logger.info(
            "sb_material_core 19.0.1.3.0 migration: mrp.bom.line has no "
            "material_id field (sb_material_mrp not installed) — "
            "skipping dependent BoM-line recompute.",
        )
        return 0
    if not products:
        return 0

    lines = BomLine.sudo().search([("product_id", "in", products.ids)])
    if not lines:
        return 0

    # Step 1: material_id is the newly-stale field (depends=["product_id"],
    # which didn't change — only its template's fallback did, invisible
    # to the ORM dependency graph). Force + flush it first.
    material_field = BomLine._fields["material_id"]
    env.add_to_compute(material_field, lines)
    material_field.recompute(lines)
    lines.flush_recordset(["material_id"])

    # Step 2: component_weight_kg / component_volume_mm3 share one compute
    # method and read material_id — force + flush them now that it's fresh.
    if "component_weight_kg" in BomLine._fields:
        weight_field = BomLine._fields["component_weight_kg"]
        volume_field = BomLine._fields["component_volume_mm3"]
        env.add_to_compute(weight_field, lines)
        env.add_to_compute(volume_field, lines)
        weight_field.recompute(lines)
        lines.flush_recordset(["component_weight_kg", "component_volume_mm3"])

    return len(lines)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "sb_material_core 19.0.1.3.0 migration: linking live BoM "
        "sheet-good component products to a material via the new "
        "product.template.material_id fallback (from %s)", version,
    )
    updated_products = _link_component_materials(env)
    _logger.info(
        "sb_material_core 19.0.1.3.0 migration: %s product(s) linked.",
        len(updated_products),
    )
    n_lines = _recompute_dependent_bom_lines(env, updated_products)
    _logger.info(
        "sb_material_core 19.0.1.3.0 migration: %s mrp.bom.line(s) "
        "recomputed.", n_lines,
    )
