# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.11.0 — force recompute after the 1.10.0 role curation.

1.10.0 rewrote PLY34/MDF12 panel_role_ids AND recomputed in the SAME
transaction; the ownership scan for a SIBLING material (MEL58's line reads
PLY34's roles) read stale cached values, so material_demand_is_exact did not
flip. Now that the roles are committed (prior version), invalidate + recompute
in this fresh transaction so the sibling-role change is honored. Idempotent.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    BomLine = env["mrp.bom.line"]
    if "material_demand_is_exact" not in BomLine._fields:
        return
    lines = BomLine.search([])
    if not lines:
        return
    env.invalidate_all()
    fields_ = [f for f in (
        "material_demand_qty", "material_demand_is_exact", "component_weight_kg",
        "component_volume_mm3", "suggested_purchase_qty",
        "suggested_purchase_uom_id") if f in BomLine._fields]
    for f in fields_:
        env.add_to_compute(lines._fields[f], lines)
    lines.flush_recordset(fields_)
    nex = len(lines.filtered("material_demand_is_exact"))
    _logger.info("cutlist 1.11.0: recomputed %s lines; %s exact.", len(lines), nex)
