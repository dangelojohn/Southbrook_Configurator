# SPDX-License-Identifier: LGPL-3.0-only
"""Re-seed training items from newly added slides.

The post_init_hook only fires on first install. When new courses ship in
southbrook_elearning_internal, the hub catalog drifts behind. This
migration picks up the slack: it runs the same seed function on every
-u of the hub addon.

The seed is idempotent — keyed by ``source_ref = "slide.slide:<id>"``,
so existing items are preserved.
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
        "southbrook_training_hub 19.0.1.1.0: re-seeding training items "
        "from slides (idempotent)")
    _seed_training_items_from_slides(env)
