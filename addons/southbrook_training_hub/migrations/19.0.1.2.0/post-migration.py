# SPDX-License-Identifier: LGPL-3.0-only
"""Re-seed training items after Wave 1b lessons land.

Same idempotent re-seed pattern as the 19.0.1.1.0 migration. Picks up
the ~19 new slides from Courses 18-21 (Quality / Payroll / Finance /
Exec persona tracks) into the hub catalog.
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
        "southbrook_training_hub 19.0.1.2.0: re-seeding training items "
        "for Wave 1b persona courses (idempotent)")
    _seed_training_items_from_slides(env)
