# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.13.0 — recompute bom-line demand/exact/weight/suggested after the
sb_material_core role curation (PLY34->shelf, MDF12->shelf).

WHY HERE (not in sb_material_core): sb_material_mrp DEPENDS on sb_material_core,
so core loads first and its post-migrate runs BEFORE this module adds
material_demand_is_exact to mrp.bom.line — the core migrations' recompute block
hit `material_demand_is_exact not in _fields` and returned early. This migration
runs in mrp's own load phase (fields present) with core's role changes already
committed, so the sibling-ownership recompute now flips correctly. Direct
compute calls (add_to_compute+flush proved unreliable here). Idempotent.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env["mrp.bom.line"].search([])
    if not lines:
        return
    env.invalidate_all()
    for meth in ("_compute_material_id", "_compute_material_demand_qty",
                 "_compute_component_weight", "_compute_suggested_purchase_qty"):
        if hasattr(lines, meth):
            getattr(lines, meth)()
    BomLine = env["mrp.bom.line"]
    flds = [f for f in (
        "material_id", "material_demand_qty", "material_demand_is_exact",
        "component_weight_kg", "component_volume_mm3", "suggested_purchase_qty",
        "suggested_purchase_uom_id") if f in BomLine._fields]
    lines.flush_recordset(flds)
    nex = len(lines.filtered("material_demand_is_exact"))
    _logger.info("cutlist mrp 1.13.0: recomputed %s lines; %s now EXACT.",
                 len(lines), nex)
