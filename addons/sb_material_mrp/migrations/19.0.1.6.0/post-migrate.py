# SPDX-License-Identifier: LGPL-3.0-only
"""
19.0.1.6.0 — Unconditional full recompute of stale stored
``mrp.bom.line.material_id`` (and the dependent stored weight/volume/
demand/purchase fields).

Why: sb_material_core 19.0.1.5.0 relinked legacy sheet components
(e.g. ``RM-MELAMINE_WHITE_5_8`` -> ``product.template.material_id`` =
``MEL58``, ``RM-HARDBOARD_1_4`` -> ``HB14``) so the thickness-specific
material would replace the generic thickness-less fallback (e.g.
``melamine``). Empirically confirmed live: ``_resolve_material()``
returns the correct thickness-specific material, but the stored
``mrp.bom.line.material_id`` was still reading the stale generic
value after that migration ran — its targeted recompute did not
persist (a migration-context recompute subtlety, not chased here).
This mirrors the known-good 19.0.1.1.1 idiom exactly, but recomputes
ALL bom lines unconditionally rather than a targeted subset, and also
recomputes the fields further downstream of ``material_id``
(``material_demand_qty`` / ``suggested_purchase_qty``) that were left
stale by the same root cause.

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
            "sb_material_mrp 19.0.1.6.0 migration: no bom lines, nothing "
            "to recompute (from %s).", version,
        )
        return

    env.add_to_compute(lines._fields["material_id"], lines)
    lines.flush_recordset(["material_id"])

    env.add_to_compute(lines._fields["component_weight_kg"], lines)
    env.add_to_compute(lines._fields["component_volume_mm3"], lines)
    env.add_to_compute(lines._fields["material_demand_qty"], lines)
    env.add_to_compute(lines._fields["suggested_purchase_qty"], lines)
    lines.flush_recordset([
        "component_weight_kg",
        "component_volume_mm3",
        "material_demand_qty",
        "suggested_purchase_qty",
    ])

    nonzero = len(
        [line for line in lines if line.component_weight_kg > 0]
    )
    _logger.info(
        "sb_material_mrp 19.0.1.6.0 migration: recomputed material_id + "
        "stored weight/volume/demand/purchase on %s bom line(s); %s now "
        "carry non-zero weight (from %s).", len(lines), nonzero, version,
    )
