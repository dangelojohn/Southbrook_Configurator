# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.7.0 — Cutlist Precision Task 4: assign panel roles (`sb.panel.
role`, Task 1) to the LEGACY (non-seeded, hand-created pre-existing)
`southbrook.kitchen.material` records by `code`, backfill the same roles
onto any already-installed copy of the SEEDED materials the data-file
change can't reach, then force-recompute the `mrp.bom.line` fields that
are now stale because of it.

Background: `data/material_seed_data.xml` (this same version bump) adds
`panel_role_ids` directly to the SEEDED materials (`mat_mdf_34`,
`mat_particle_34`, `mat_melamine_34`, `mat_mel_58`, `mat_ply_34` -> box
roles; `mat_ply_14_back`, `mat_hardboard_14` -> back). On a FRESH
install that's sufficient — the record is created with roles already
set. On an UPGRADE of a DB where `sb_material_core` was already
installed (these xml_ids already exist in `ir_model_data`), `noupdate=
"1"` means Odoo's data loader SKIPS re-applying that record entirely on
`-u` — by design, so a shop's own hand-edits to a noupdate record
survive a later upgrade — which also means a brand-new field VALUE
added to an EXISTING noupdate record's `<record>` never reaches an
already-installed DB through the data file alone (confirmed empirically
running this migration against a DB with `sb_material_core` already at
19.0.1.6.0: the seeded materials came out of `-u` still role-less).
`_assign_seeded_role_backfill()` below closes that gap the same
idempotent way `_assign_legacy_roles()` does for the legacy catalog —
mirrors the 19.0.1.3.0/19.0.1.5.0 migrations' established idiom of a
Python-level backfill for values a noupdate data-file change can't
retroactively apply.

This migration is ALSO responsible for the OTHER `southbrook.kitchen.
material` records: the 10-record legacy catalog seeded by
`southbrook_mrp_kitchen_workcenters/data/southbrook_kitchen_materials.xml`
(`code='mdf'/'melamine'/'plywood'/'particle_board'/'solid_wood'/...`),
created before `sb.panel.role` existed and therefore never assigned any.

Mapping (by `code`, CONFIRMED against southbrook_kitchen_materials.xml):
    mdf, melamine, plywood, particle_board, solid_wood
        -> box roles (side_L, side_R, top, bottom) — all five are
           routinely used as carcass box sheet goods on the shop floor.
    (no clearly-back legacy code exists today — laminate/veneer/quartz/
    stone/solid_surface are facing or countertop materials, not backs —
    so `_LEGACY_BACK_CODES` is empty; documented here rather than left
    to a silent no-op so a future back-ish legacy code is an obvious
    one-line addition, not a rediscovery.)

Idempotent + non-destructive: a material (legacy OR seeded) is only
ever touched when its `panel_role_ids` is CURRENTLY EMPTY — a shop that
has since hand-assigned roles (its own choice, possibly different from
the standard default) is never overwritten. Materials not in the maps,
or already carrying roles, are left untouched.

After assigning roles, `mrp.bom.line.material_demand_qty` /
`material_demand_is_exact` / `component_weight_kg` / `component_volume_
mm3` are potentially stale for every line on any BoM touching one of
the now-role-bearing materials — ownership (`_sb_line_owned_roles()`,
Task 2/3) is computed by walking ALL lines of a BoM in Python, not
through an ORM-visible `@api.depends` chain, so a targeted recompute
would have to reimplement that ownership walk just to scope it. Instead
this mirrors the `sb_material_mrp` 19.0.1.7.0 migration's approach
exactly: an unconditional full recompute of every `mrp.bom.line`'s
demand/weight/volume/exact fields — recomputing stored computes is
always safe to re-run.

Soft-guarded: `sb_material_mrp` is not a manifest dependency of
`sb_material_core` (it's the other way around), so `mrp.bom.line` may
not carry these fields at all when this runs (e.g. `sb_material_core`
upgraded alone) — skip the recompute step silently in that case; the
material-level role assignment itself is unaffected.
"""

import logging

_logger = logging.getLogger(__name__)

# Legacy `southbrook.kitchen.material.code` -> box roles (xml_ids in
# sb_material_core.data.sb_panel_role_data).
_LEGACY_BOX_CODES = {"mdf", "melamine", "plywood", "particle_board", "solid_wood"}
# No clearly-back legacy code exists today (see module docstring) —
# kept as an explicit empty set rather than omitted.
_LEGACY_BACK_CODES = set()

_BOX_ROLE_XML_IDS = (
    "sb_material_core.panel_role_side_l",
    "sb_material_core.panel_role_side_r",
    "sb_material_core.panel_role_top",
    "sb_material_core.panel_role_bottom",
)
_BACK_ROLE_XML_IDS = ("sb_material_core.panel_role_back",)

# Seeded `southbrook.kitchen.material` xml_id -> role xml_id suffixes
# (relative to sb_material_core.), mirroring data/material_seed_data.xml
# exactly (see that file's Task-4 comment for the shop-convention
# rationale on why mat_ply_34/mat_melamine_34 also get `shelf`).
_SEEDED_ROLE_MAP = {
    "sb_material_core.mat_mdf_34": ("panel_role_side_l", "panel_role_side_r",
                                     "panel_role_top", "panel_role_bottom"),
    "sb_material_core.mat_particle_34": ("panel_role_side_l", "panel_role_side_r",
                                          "panel_role_top", "panel_role_bottom"),
    "sb_material_core.mat_melamine_34": ("panel_role_side_l", "panel_role_side_r",
                                          "panel_role_top", "panel_role_bottom",
                                          "panel_role_shelf"),
    "sb_material_core.mat_mel_58": ("panel_role_side_l", "panel_role_side_r",
                                     "panel_role_top", "panel_role_bottom"),
    "sb_material_core.mat_ply_34": ("panel_role_side_l", "panel_role_side_r",
                                     "panel_role_top", "panel_role_bottom",
                                     "panel_role_shelf"),
    "sb_material_core.mat_ply_14_back": ("panel_role_back",),
    "sb_material_core.mat_hardboard_14": ("panel_role_back",),
}


def _assign_seeded_role_backfill(env):
    """Backfill `panel_role_ids` onto already-installed copies of the
    SEEDED materials whose noupdate record predates this version's data
    file (see module docstring). Only touches a material whose
    `panel_role_ids` is currently empty. Returns the recordset updated.
    """
    Material = env["southbrook.kitchen.material"]
    updated = Material.browse()

    for material_ref, role_suffixes in _SEEDED_ROLE_MAP.items():
        material = env.ref(material_ref, raise_if_not_found=False)
        if not material:
            _logger.info(
                "sb_material_core 19.0.1.7.0 migration: seeded material "
                "%s not found -- skipping (fresh install not yet loaded, "
                "or module not installed).", material_ref,
            )
            continue
        if material.panel_role_ids:
            continue

        roles = env["sb.panel.role"].browse()
        for suffix in role_suffixes:
            role = env.ref(f"sb_material_core.{suffix}", raise_if_not_found=False)
            if role:
                roles |= role
        if not roles:
            continue

        material.write({"panel_role_ids": [(6, 0, roles.ids)]})
        updated |= material
        _logger.info(
            "sb_material_core 19.0.1.7.0 migration: backfilled role(s) "
            "%s onto seeded material %s (noupdate skipped it on -u).",
            roles.mapped("code"), material_ref,
        )

    return updated


def _assign_legacy_roles(env):
    """Assign box/back panel roles to legacy materials still lacking any,
    by `code`. Returns the `southbrook.kitchen.material` recordset
    actually updated (informational + used to scope the log message;
    the dependent-BoM-line recompute below is unconditional/global).
    """
    Material = env["southbrook.kitchen.material"]
    updated = Material.browse()

    def _resolve_roles(xml_ids):
        roles = env["sb.panel.role"].browse()
        for xml_id in xml_ids:
            role = env.ref(xml_id, raise_if_not_found=False)
            if role:
                roles |= role
        return roles

    box_roles = _resolve_roles(_BOX_ROLE_XML_IDS)
    back_roles = _resolve_roles(_BACK_ROLE_XML_IDS)

    for codes, roles, label in (
        (_LEGACY_BOX_CODES, box_roles, "box"),
        (_LEGACY_BACK_CODES, back_roles, "back"),
    ):
        if not codes or not roles:
            continue
        materials = Material.search([("code", "in", sorted(codes))])
        for material in materials:
            if material.panel_role_ids:
                _logger.info(
                    "sb_material_core 19.0.1.7.0 migration: material "
                    "code=%s already has panel roles %s -- leaving "
                    "untouched.", material.code,
                    material.panel_role_ids.mapped("code"),
                )
                continue
            material.write({"panel_role_ids": [(6, 0, roles.ids)]})
            updated |= material
            _logger.info(
                "sb_material_core 19.0.1.7.0 migration: assigned %s "
                "role(s) %s to legacy material code=%s.",
                label, roles.mapped("code"), material.code,
            )

    return updated


def _recompute_all_bom_lines(env):
    """Mirror the `sb_material_mrp` 19.0.1.7.0 migration exactly: force
    an unconditional full recompute of the demand/weight/volume/exact
    fields on every `mrp.bom.line`. Skips silently when `sb_material_mrp`
    is not installed (those fields won't exist on `mrp.bom.line`).
    """
    BomLine = env["mrp.bom.line"]
    if "material_demand_is_exact" not in BomLine._fields:
        _logger.info(
            "sb_material_core 19.0.1.7.0 migration: mrp.bom.line has no "
            "material_demand_is_exact field (sb_material_mrp not "
            "installed) -- skipping dependent BoM-line recompute.",
        )
        return 0

    lines = BomLine.search([])
    if not lines:
        _logger.info(
            "sb_material_core 19.0.1.7.0 migration: no bom lines, "
            "nothing to recompute.",
        )
        return 0

    for fname in ("material_demand_qty", "material_demand_is_exact",
                  "component_weight_kg", "component_volume_mm3"):
        if fname in BomLine._fields:
            env.add_to_compute(lines._fields[fname], lines)
    lines.flush_recordset([
        "material_demand_qty", "material_demand_is_exact",
        "component_weight_kg", "component_volume_mm3",
    ])

    exact_count = len([line for line in lines if line.material_demand_is_exact])
    _logger.info(
        "sb_material_core 19.0.1.7.0 migration: recomputed %s bom "
        "line(s); %s now exact.", len(lines), exact_count,
    )
    return len(lines)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "sb_material_core 19.0.1.7.0 migration: backfilling seeded-"
        "material roles + assigning panel roles to legacy materials "
        "still lacking any (from %s).", version,
    )
    seeded_updated = _assign_seeded_role_backfill(env)
    _logger.info(
        "sb_material_core 19.0.1.7.0 migration: %s seeded material(s) "
        "backfilled.", len(seeded_updated),
    )
    legacy_updated = _assign_legacy_roles(env)
    _logger.info(
        "sb_material_core 19.0.1.7.0 migration: %s legacy material(s) "
        "assigned roles.", len(legacy_updated),
    )
    _recompute_all_bom_lines(env)
