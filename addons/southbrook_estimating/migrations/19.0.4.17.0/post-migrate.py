# SPDX-License-Identifier: LGPL-3.0-only
"""
19.0.4.17.0 — backfill default_val on single-value attribute lines.

post_init_hook only fires on -i. The live southbrook stack is already
installed, so the backfill in __init__.py would never reach the
existing attribute_lines without this migration.

The function itself is idempotent (only writes lines where default_val
is currently unset), so it is safe to re-run.

This unlocks the view-side hide of single-value selectors: the wizard
inherits in views/product_configurator_wizard_view.xml gate
visibility on default_val being set, so any line that didn't get
backfilled here will still render visibly (user is never stranded).
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.southbrook_estimating import (
        _backfill_single_value_attribute_defaults,
    )

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "southbrook_estimating 19.0.4.17.0 migration: backfilling "
        "default_val on single-value attribute lines (from %s)", version,
    )
    _backfill_single_value_attribute_defaults(env)
