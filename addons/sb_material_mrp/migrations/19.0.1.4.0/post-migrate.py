# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.4.0 — populate suggested_purchase_qty/_uom on existing lines."""
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
    env.add_to_compute(lines._fields["suggested_purchase_qty"], lines)
    env.add_to_compute(lines._fields["suggested_purchase_uom_id"], lines)
    lines.flush_recordset(["suggested_purchase_qty", "suggested_purchase_uom_id"])
    _logger.info(
        "sb_material_mrp 19.0.1.4.0: recomputed suggested_purchase_qty on %s "
        "line(s) (from %s).", len(lines), version,
    )
