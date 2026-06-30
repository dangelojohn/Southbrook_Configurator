# SPDX-License-Identifier: LGPL-3.0-only
"""
19.0.4.4.0 — apply Southbrook report branding to res.company on upgrade.

post_init_hook only fires on first install (-i), never on -u. For the
LIVE southbrook stack — already installed at 19.0.4.3.0 — the branding
configured by _configure_southbrook_report_branding in __init__.py would
otherwise never reach res.company without this migration.

The function itself is idempotent (only writes fields that drifted), so
it's safe whether the live company is currently default-placeholder or
partially configured.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    # Absolute import via Odoo's addon-loader path. Relative imports do
    # not work in migration scripts (they're loaded by imp.load_source,
    # not as part of a Python package).
    from odoo.addons.southbrook_estimating import _configure_southbrook_report_branding

    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info(
        "southbrook_estimating 19.0.4.4.0 migration: "
        "applying report branding to res.company (upgrade from %s)",
        version,
    )
    _configure_southbrook_report_branding(env)
