# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.10.0 — Cutlist role curation (Decision 1a + MDF12, 2026-07-27).

noupdate seed does NOT re-apply panel_role_ids to existing materials on -u, so
this migration applies the curation to the live records:
  - PLY34 (mat_ply_34): box+shelf -> shelf ONLY, so melamine (MEL58) is the
    unique carcass-box owner on cabinets listing both -> resolves the box
    ambiguity (6 shorthand BoM melamine lines flip to exact).
  - MDF12 (mat_mdf_12): (none) -> shelf.
  - PLY12 deliberately left with no role (a cabinet's back is the 1/4" ply-back;
    the 1/2" ply has no unique material-level role on those BoMs -> stays on the
    honest estimate).

Only rewrites when the current roles match the prior seeded value (never
clobbers a shop hand-edit). Then recomputes dependent mrp.bom.line fields.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    ref = env.ref
    shelf = ref("sb_material_core.panel_role_shelf", raise_if_not_found=False)
    box = env["sb.panel.role"].search([
        ("code", "in", ["side_L", "side_R", "top", "bottom"])])
    if not shelf:
        _logger.warning("cutlist curation 1.10.0: shelf role missing, skipping.")
        return

    ply34 = ref("sb_material_core.mat_ply_34", raise_if_not_found=False)
    if ply34:
        cur = set(ply34.panel_role_ids.mapped("code"))
        if cur == {"side_L", "side_R", "top", "bottom", "shelf"}:
            ply34.panel_role_ids = [(6, 0, shelf.ids)]
            _logger.info("cutlist curation: PLY34 box+shelf -> shelf only.")

    mdf12 = ref("sb_material_core.mat_mdf_12", raise_if_not_found=False)
    if mdf12 and not mdf12.panel_role_ids:
        mdf12.panel_role_ids = [(6, 0, shelf.ids)]
        _logger.info("cutlist curation: MDF12 -> shelf.")

    BomLine = env["mrp.bom.line"]
    if "material_demand_is_exact" not in BomLine._fields:
        return
    lines = BomLine.search([])
    if not lines:
        return
    for fname in ("material_demand_qty", "material_demand_is_exact",
                  "component_weight_kg", "component_volume_mm3",
                  "suggested_purchase_qty", "suggested_purchase_uom_id"):
        if fname in BomLine._fields:
            env.add_to_compute(lines._fields[fname], lines)
    lines.flush_recordset([f for f in (
        "material_demand_qty", "material_demand_is_exact", "component_weight_kg",
        "component_volume_mm3", "suggested_purchase_qty",
        "suggested_purchase_uom_id") if f in BomLine._fields])
    _logger.info("cutlist curation 1.10.0: recomputed %s bom line(s).", len(lines))
