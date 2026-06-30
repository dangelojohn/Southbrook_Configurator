# SPDX-License-Identifier: LGPL-3.0-only
"""Re-seed training items after Wave 2 module deep-dive lessons land.

Same idempotent re-seed pattern as the 19.0.1.1.0 + 19.0.1.2.0 migrations.
Picks up the ~49 new slides from Courses 22-28 (module deep-dives for
Quality, Payroll CA, Finance Pack, Integrations, MES+MPS, CMMS+WMS, Exec
Dashboard) into the hub catalog.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    from odoo.addons.southbrook_training_hub.hooks import (
        _seed_training_items_from_slides,
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "southbrook_training_hub 19.0.1.3.0: re-seeding training items "
        "for Wave 2 module deep-dives (idempotent)")
    _seed_training_items_from_slides(env)
