# SPDX-License-Identifier: LGPL-3.0-only
"""T6 (kitchen templates) — recompute stored design totals.

total_cabinets now EXCLUDES filler strips and the new filler_count
carries them; stored computes do not self-recompute on -u, so every
existing design gets a direct recompute here (archived ones included).
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    designs = env["southbrook.kitchen.design"].with_context(
        active_test=False).search([])
    designs._compute_totals()
    _logger.info("[19.0.5.32.0] recomputed totals for %d designs",
                 len(designs))
