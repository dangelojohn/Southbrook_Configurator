# SPDX-License-Identifier: LGPL-3.0-only
"""
19.0.1.2.0 — Sibling weight-attribution fix: recompute stale stored
``mrp.bom.line.component_volume_mm3`` / ``component_weight_kg``.

Why: before this version, every ``density_volume`` bom line got the
FULL cabinet carcass volume from ``_panel_volume_mm3``, regardless of
how many sibling lines on the same BoM also referenced the same sheet
product. A configurator-built BoM has exactly one such line, so this
was invisible there — but live hand-built/imported BoMs repeat the
same sheet product across several per-panel lines (observed live: BoM
256, 5x SBK-SHEET-MB34-WW; BoMs 280-286, several sheet lines each),
and each of those lines stored the WHOLE carcass, over-counting the
BoM's total material weight by roughly the sibling count (live: B24 =
247.98 kg vs a realistic ~35-40 kg).

The model now divides each density_volume line's carcass volume by the
qty-weighted total of its density_volume siblings
(``_sb_component_share_volume_mm3``) for all FUTURE computes; this
migration repairs the rows that were already stored under the old,
un-shared formula. Mirrors the 19.0.1.1.1 migration's
add_to_compute/flush pattern exactly.

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
            "sb_material_mrp 19.0.1.2.0 migration: no bom lines, nothing "
            "to recompute (from %s).", version,
        )
        return
    env.add_to_compute(lines._fields["component_weight_kg"], lines)
    env.add_to_compute(lines._fields["component_volume_mm3"], lines)
    lines.flush_recordset(["component_weight_kg", "component_volume_mm3"])
    nonzero = len(
        [line for line in lines if line.component_weight_kg > 0]
    )
    _logger.info(
        "sb_material_mrp 19.0.1.2.0 migration: recomputed stored "
        "component_weight_kg/component_volume_mm3 (sibling-share "
        "attribution) on %s bom line(s); %s now carry non-zero weight "
        "(from %s).", len(lines), nonzero, version,
    )
