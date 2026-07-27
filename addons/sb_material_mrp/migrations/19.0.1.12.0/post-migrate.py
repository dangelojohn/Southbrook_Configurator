# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.12.0 — relabel suggested_purchase_uom_id: yield-based suggestions are
a COUNT of purchase units (sheets), shown in Units, not the product's m²
stocking UoM. Recompute the stored field on all bom lines (idempotent)."""
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
    for fname in ("suggested_purchase_qty", "suggested_purchase_uom_id"):
        env.add_to_compute(lines._fields[fname], lines)
    lines.flush_recordset(["suggested_purchase_qty", "suggested_purchase_uom_id"])
    _logger.info(
        "sb_material_mrp 19.0.1.12.0: recomputed suggested-qty UoM on %s "
        "bom line(s) (from %s).", len(lines), version,
    )
