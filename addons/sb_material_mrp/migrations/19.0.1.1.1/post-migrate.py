# SPDX-License-Identifier: LGPL-3.0-only
"""
19.0.1.1.1 — Repair Wave 3 follow-through: recompute stale stored
``mrp.bom.line.material_id`` (and the dependent stored weight/volume).

Why: ``material_id`` is a stored compute that, before this version,
depended only on ``product_id``. Wave 3 (sb_material_core 19.0.1.3.0)
linked 6 live sheet components to materials via the NEW
``product.template.material_id`` fallback — but that write never
touched ``product_id``, so every existing bom line kept its stale
empty ``material_id`` and the whole weight chain still multiplied to 0
(observed live 2026-07-26). The model now carries the dotted dep
``product_id.product_tmpl_id.material_id`` for future edits; this
migration repairs the rows that went stale before the dep existed.

Idempotent: recomputing computed fields is always safe to re-run.
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
            "sb_material_mrp 19.0.1.1.1 migration: no bom lines, nothing "
            "to recompute (from %s).", version,
        )
        return
    env.add_to_compute(lines._fields["material_id"], lines)
    lines.flush_recordset(["material_id"])
    env.add_to_compute(lines._fields["component_weight_kg"], lines)
    env.add_to_compute(lines._fields["component_volume_mm3"], lines)
    lines.flush_recordset(["component_weight_kg", "component_volume_mm3"])
    nonzero = len(
        [line for line in lines if line.component_weight_kg > 0]
    )
    _logger.info(
        "sb_material_mrp 19.0.1.1.1 migration: recomputed material_id + "
        "stored weight on %s bom line(s); %s now carry non-zero weight "
        "(from %s).", len(lines), nonzero, version,
    )
