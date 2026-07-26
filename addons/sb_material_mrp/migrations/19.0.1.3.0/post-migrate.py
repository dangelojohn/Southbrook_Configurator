# SPDX-License-Identifier: LGPL-3.0-only
"""19.0.1.3.0 — populate the new stored material_demand_qty on existing
BoM lines (idempotent: recomputing a stored compute is always safe)."""
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
    env.add_to_compute(lines._fields["material_demand_qty"], lines)
    lines.flush_recordset(["material_demand_qty"])
    _logger.info(
        "sb_material_mrp 19.0.1.3.0: recomputed material_demand_qty on %s "
        "bom line(s) (from %s).", len(lines), version,
    )
