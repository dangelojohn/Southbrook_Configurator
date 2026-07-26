# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.7.0 — recompute demand/weight now that exact panel-role volume is
wired (idempotent; recomputing stored computes is always safe).

Why: Cutlist Precision Task 3 changed the VOLUME SOURCE the density_volume/
density_area branches of `_compute_material_demand_qty` and
`_compute_component_weight` use — preferring the exact per-owned-role
volume (`_sb_line_exact_volume_mm3`, Task 2) over the qty-weighted carcass
estimate (`_sb_component_share_volume_mm3`) whenever a line's material
uniquely owns one or more panel roles on its BoM. Every stored line that
predates this change (and every line whose material had a role assigned by
Task 1's data but was never recomputed since) is stale until this migration
forces a full recompute — mirrors the 19.0.1.6.0 idiom exactly.
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
        _logger.info(
            "sb_material_mrp 19.0.1.7.0 migration: no bom lines, nothing "
            "to recompute (from %s).", version,
        )
        return

    # suggested_purchase_qty @api.depends on material_demand_qty, so it must
    # recompute too when demand values flip exact<->fallback — mirroring the
    # 19.0.1.6.0 migration's precedent (migration-context depend cascades are
    # unreliable, so recompute it explicitly rather than trusting the cascade).
    for fname in ("material_demand_qty", "material_demand_is_exact",
                  "component_weight_kg", "component_volume_mm3",
                  "suggested_purchase_qty"):
        env.add_to_compute(lines._fields[fname], lines)
    lines.flush_recordset(["material_demand_qty", "material_demand_is_exact",
                           "component_weight_kg", "component_volume_mm3",
                           "suggested_purchase_qty"])

    exact_count = len([line for line in lines if line.material_demand_is_exact])
    _logger.info(
        "cutlist 19.0.1.7.0: recomputed %s lines (%s now exact) (from %s).",
        len(lines), exact_count, version,
    )
