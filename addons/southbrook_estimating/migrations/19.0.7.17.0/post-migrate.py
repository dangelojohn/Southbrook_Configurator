# SPDX-License-Identifier: LGPL-3.0-only
"""
19.0.7.17.0 — Repair Wave 2, Upgrade 2: re-run the geometry backfill now
that `_SKU_DEFAULTS` carries the 7 live shorthand `default_code`s
(B24, DB24, SB-BASE-3DRW, SB30, T24, W24, W24-2) that weren't in the
table when 19.0.7.16.0 first ran. Those variants' `default_code`s
matched no row at the time, so `_sb_backfill_geometry()` honestly left
them at 0/0/0. FP3 (filler panel) is deliberately still excluded from
the table (no carcass to assign) and stays at 0/0/0 — see the comment
in `product_config_line.py` immediately after the `W24-2` row.

`_sb_backfill_geometry()` itself is idempotent (only touches variants
where all three dimensions are currently 0, and honestly leaves
unknown-SKU variants untouched), so it is safe to re-run — this is the
exact same call the 19.0.7.16.0 migration made, just re-run after the
table gained more rows. It also benefits from Wave-1 FIX-B: the
dependent BoM-weight recompute (`_sb_recompute_dependent_bom_weights`)
now covers template-level BoMs too, so any template-level BoM lines
pointing at these newly-resolved variants get their stored weight
refreshed in the same pass.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "southbrook_estimating 19.0.7.17.0 migration: re-running "
        "_sb_backfill_geometry() now that _SKU_DEFAULTS covers the live "
        "shorthand SKUs (B24, DB24, SB-BASE-3DRW, SB30, T24, W24, "
        "W24-2) (from %s)", version,
    )
    updated = env["product.product"]._sb_backfill_geometry()
    _logger.info(
        "southbrook_estimating 19.0.7.17.0 migration: %s variant(s) "
        "updated.", updated,
    )
