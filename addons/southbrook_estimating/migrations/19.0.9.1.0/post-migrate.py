# SPDX-License-Identifier: LGPL-3.0-only
"""T4a (kitchen templates) — SB-CORNER variant data repair.

Variant Width '33 in' -> '36 in' (the outlier vs 3 other data points),
LH default_code backfill, RH twin variant creation. All idempotent —
see models/corner_sku_repair.py for the ground-truth citation.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo.addons.southbrook_estimating.models.corner_sku_repair import (
        repair_corner_sku,
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("[19.0.9.1.0] corner SKU repair: %s",
                 repair_corner_sku(env))
