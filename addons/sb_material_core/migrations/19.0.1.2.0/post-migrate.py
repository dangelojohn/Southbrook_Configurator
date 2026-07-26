# SPDX-License-Identifier: LGPL-3.0-only
"""
19.0.1.2.0 — Repair Wave 2, Upgrade 1: assign family_id (+ density where
the CONFIRMED mapping table carries one) to the 10 pre-existing
`southbrook.kitchen.material` records seeded by
southbrook_mrp_kitchen_workcenters (mdf, plywood, particle_board,
melamine, solid_wood, quartz, stone, laminate, veneer, solid_surface).

Those records predate this module's `family_id` field, so on the live
DB every one of them sits at family_id=False -> effective_density=0 ->
every downstream weight calc (sb_material_mrp) multiplies to zero.

`_sb_backfill_family_density()` itself is idempotent (only matches
`code=<mapped code>` AND `family_id=False`, and only writes
density/density_source when the mapping carries a density AND the
record's current density is 0), so it is safe to re-run.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "sb_material_core 19.0.1.2.0 migration: backfilling family_id "
        "(+ density where mapped) on pre-existing materials via "
        "_sb_backfill_family_density() (from %s)", version,
    )
    updated = env["southbrook.kitchen.material"]._sb_backfill_family_density()
    _logger.info(
        "sb_material_core 19.0.1.2.0 migration: %s material(s) updated.",
        updated,
    )
