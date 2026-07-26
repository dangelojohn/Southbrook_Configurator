# SPDX-License-Identifier: LGPL-3.0-only
"""
19.0.7.16.0 — backfill sb_width_mm/height_mm/depth_mm (and their
downstream per-line component_weight_kg) on existing variants via
product.product._sb_backfill_geometry().

post_init_hook only fires on -i. The live southbrook stack is already
installed, so the geometry-writeback branch's post_init_hook chain
would never reach existing variants without this migration — they
would stay at 0/0/0 forever on a plain -u.

_sb_backfill_geometry() itself is idempotent (only touches variants
where all three dimensions are currently 0, and honestly leaves
unknown-SKU variants untouched), so it is safe to re-run.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "southbrook_estimating 19.0.7.16.0 migration: backfilling "
        "sb_width_mm/height_mm/depth_mm on existing variants via "
        "_sb_backfill_geometry() (from %s)", version,
    )
    env["product.product"]._sb_backfill_geometry()
