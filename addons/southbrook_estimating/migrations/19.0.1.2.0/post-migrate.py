# SPDX-License-Identifier: LGPL-3.0-only
"""
Phase 2C — backfill missing product.template.attribute.line rows.

Context
-------
The June 2026 configurator audit (commit 0824b1a) added 77 new
product.template.attribute.line records via XML record blocks in
data/product_templates.xml to wire 10 new audit attributes (frame_style,
door_overlay, wood_species, drawer_construction, pull_finish,
interior_storage, lighting, glass_insert, edge_profile, crown_molding)
to each of the 12 Q8-locked cabinet templates.

On the live southbrook stack, the XML upgrade produced asymmetric results:

  | cabinet     | got new attrs? |
  |-------------|----------------|
  | SB-CORNER   | yes (full)     |
  | SB-DRAWER   | yes (full)     |
  | SB-VANITY   | yes (full)     |
  | SB-SINK-BASE| yes (full)     |
  | SB-WALL-1DR | no — silent skip
  | SB-WALL-2DR | no
  | SB-BASE-1DR | no
  | SB-BASE-2DR | no
  | SB-TALL-PANTRY | no
  | SB-TALL-OVEN| no

Inspection showed that NONE of those 6 cabinets' attribute_lines were
registered in ir.model.data after the initial install — Odoo's record
loader did create their rows from XML during install but never wrote
the xml_id entries. On subsequent upgrades, the loader silently
skipped ADDING new attribute_lines for those 6 templates.

This migration is the deterministic fix: on upgrade to 19.0.1.2.0,
walk the same per-cabinet attribute matrix the XML defines, and for
each (template, attribute) pair where the line is missing, create it
via ORM and register its xml_id.

The script is idempotent — safe to re-run.
"""
import logging

_logger = logging.getLogger(__name__)

# 6 cabinets where the XML upgrade silently dropped attribute_lines.
# Each maps to a set of "kind" markers driving which attributes apply.
TARGETS = {
    "wall_1dr":    {"wall"},
    "wall_2dr":    {"wall"},
    "base_1dr":    {"drawer", "interior"},
    "base_2dr":    {"drawer", "interior"},
    "tall_pantry": {"drawer", "interior"},
    "tall_oven":   set(),
}

# Universal set — applies to every TARGETS cabinet.
UNIVERSAL = [
    ("attr_frame_style", [
        "value_frame_framed", "value_frame_frameless",
    ]),
    ("attr_door_overlay", [
        "value_overlay_full", "value_overlay_partial",
        "value_overlay_inset", "value_overlay_beaded_inset",
    ]),
    ("attr_wood_species", [
        "value_species_maple", "value_species_cherry",
        "value_species_red_oak", "value_species_white_oak_rift",
        "value_species_walnut", "value_species_alder",
        "value_species_hickory", "value_species_mdf_painted",
    ]),
    ("attr_pull_finish", [
        "value_pull_polished_nickel", "value_pull_brushed_nickel",
        "value_pull_matte_black", "value_pull_antique_bronze",
        "value_pull_brushed_brass", "value_pull_polished_chrome",
        "value_pull_oil_rubbed_bronze", "value_pull_champagne_bronze",
    ]),
    ("attr_edge_profile", [
        "value_edge_square", "value_edge_eased", "value_edge_bevel",
        "value_edge_ogee", "value_edge_bullnose",
    ]),
    ("attr_lighting", [
        "value_lighting_none", "value_lighting_under_cabinet_led",
        "value_lighting_toekick_led", "value_lighting_puck",
    ]),
]

WALL_EXTRAS = [
    ("attr_glass_insert", [
        "value_glass_none", "value_glass_clear", "value_glass_frosted",
        "value_glass_seeded", "value_glass_reeded", "value_glass_leaded",
    ]),
    ("attr_crown_molding", [
        "value_crown_none", "value_crown_simple", "value_crown_ogee",
        "value_crown_stacked", "value_crown_dental",
    ]),
]

DRAWER_EXTRA = ("attr_drawer_construction", [
    "value_drawer_dovetail_hardwood", "value_drawer_plywood_5_8",
    "value_drawer_particleboard", "value_drawer_metal_blum",
])

INTERIOR_EXTRA = ("attr_interior_storage", [
    "value_int_pullout_trash", "value_int_spice_pullout",
    "value_int_knife_block", "value_int_cutlery_tray_wood",
    "value_int_lazy_susan", "value_int_rollout_tray",
    "value_int_mixer_lift", "value_int_wine_rack",
    "value_int_charging_drawer", "value_int_tipout_sink",
])


def _ref(env, name):
    return env.ref("southbrook_estimating." + name, raise_if_not_found=False)


def _ensure_attribute_line(env, template, attr_xmlid, value_xmlids, cab_xmlid):
    """Create attribute_line row if missing and register the xml_id."""
    attr = _ref(env, attr_xmlid)
    if not attr:
        _logger.warning(
            "phase2c: attribute %r not found, skipping for %s",
            attr_xmlid, cab_xmlid,
        )
        return False

    Line = env["product.template.attribute.line"]
    line = Line.search([
        ("product_tmpl_id", "=", template.id),
        ("attribute_id", "=", attr.id),
    ], limit=1)
    created = False
    if not line:
        value_ids = []
        for vname in value_xmlids:
            v = _ref(env, vname)
            if not v:
                _logger.warning(
                    "phase2c: value %r missing, skipping line for %s/%s",
                    vname, cab_xmlid, attr_xmlid,
                )
                return False
            value_ids.append(v.id)
        line = Line.create({
            "product_tmpl_id": template.id,
            "attribute_id": attr.id,
            "value_ids": [(6, 0, value_ids)],
        })
        created = True

    xml_name = "attr_line_%s_%s" % (
        cab_xmlid, attr_xmlid.replace("attr_", "", 1),
    )
    IMD = env["ir.model.data"]
    if not IMD.search_count([
        ("module", "=", "southbrook_estimating"),
        ("name", "=", xml_name),
    ]):
        IMD.create({
            "module": "southbrook_estimating",
            "name": xml_name,
            "model": "product.template.attribute.line",
            "res_id": line.id,
            "noupdate": False,
        })
    return created


def migrate(cr, version):
    """Post-migrate to 19.0.1.2.0 — backfill the 6 broken cabinets."""
    if not version:
        # Fresh install — data/product_templates.xml handles wiring.
        # If even fresh installs hit the same skip pattern, this
        # script can be promoted to run unconditionally; for now we
        # treat fresh installs as the happy path.
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    created_count = 0
    present_count = 0
    missing_templates = []
    for cab_xmlid, kinds in TARGETS.items():
        template = _ref(env, cab_xmlid)
        if not template:
            missing_templates.append(cab_xmlid)
            continue

        todo = list(UNIVERSAL)
        if "wall" in kinds:
            todo.extend(WALL_EXTRAS)
        if "drawer" in kinds:
            todo.append(DRAWER_EXTRA)
        if "interior" in kinds:
            todo.append(INTERIOR_EXTRA)

        for attr_xmlid, value_xmlids in todo:
            if _ensure_attribute_line(
                env, template, attr_xmlid, value_xmlids, cab_xmlid,
            ):
                created_count += 1
            else:
                present_count += 1

    _logger.info(
        "phase2c (audit Phase 2C backfill): created=%d, already_present=%d, "
        "missing_templates=%s",
        created_count, present_count, missing_templates,
    )
