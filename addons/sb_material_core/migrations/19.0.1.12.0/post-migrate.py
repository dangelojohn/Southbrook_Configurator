# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.12.0 — reliably persist the role-curation recompute.

The 1.10.0/1.11.0 add_to_compute+flush did NOT persist material_demand_is_exact
after the sibling-role change (proven: an in-memory _compute_material_demand_qty
call yields is_exact=True, but add_to_compute+flush left the stored value False).
Call the compute methods DIRECTLY on all lines after invalidation, then flush —
the pattern verified in-memory against live data. Idempotent.
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
    # Direct compute calls (dependency order) — reliable where add_to_compute
    # wasn't. Guard each in case a sibling module isn't installed.
    for meth in ("_compute_material_id", "_compute_material_demand_qty",
                 "_compute_component_weight", "_compute_suggested_purchase_qty"):
        if hasattr(lines, meth):
            getattr(lines, meth)()
    flds = [f for f in (
        "material_id", "material_demand_qty", "material_demand_is_exact",
        "component_weight_kg", "component_volume_mm3", "suggested_purchase_qty",
        "suggested_purchase_uom_id") if f in BomLine._fields]
    lines.flush_recordset(flds)
    nex = len(lines.filtered("material_demand_is_exact"))
    _logger.info("cutlist 1.12.0: direct-recomputed %s lines; %s now EXACT.",
                 len(lines), nex)
