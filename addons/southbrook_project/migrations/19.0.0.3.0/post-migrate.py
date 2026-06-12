# SPDX-License-Identifier: LGPL-3.0-only
"""Backfill MRP readiness snapshots on module upgrade.

Fresh installs run the module post-init hook. Existing databases reach
this change through `-u southbrook_project`, so they need a migration
to populate the stored queue fields before planners open the command
center.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    tasks = env["project.task"].sudo().search([])
    if not tasks:
        _logger.info(
            "southbrook_project 19.0.0.3.0 migration: no task snapshots "
            "to refresh"
        )
        return

    tasks.action_southbrook_refresh_mrp_readiness_snapshot()
    _logger.info(
        "southbrook_project 19.0.0.3.0 migration: refreshed %s MRP "
        "readiness snapshots",
        len(tasks),
    )
