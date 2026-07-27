# SPDX-License-Identifier: LGPL-3.0-only
"""Post-install hook — backfill blank fields on project ID 1.

We can't use a data XML record because project ID 1 (the live "Test"
project) was created in the UI and has no xmlid. Doing a write via
the post_init_hook keeps the description/date fills idempotent (we only
fill blanks; we never stomp values the operator already set). The actual
blank-fill logic lives in ``project.project._southbrook_backfill_defaults``
so it is unit-testable independently of the hardcoded id-1 lookup.
"""
import logging

_logger = logging.getLogger(__name__)


def post_init_backfill_project_1(env):
    """Populate description, dates, and feature flags on project ID 1
    when those fields are blank. Safely no-ops on a fresh DB where
    project 1 doesn't exist."""
    project = env["project.project"].browse(1).exists()
    if not project:
        _logger.info(
            "southbrook_project: project ID 1 not present, skipping "
            "post-init backfill (this is fine on a fresh DB).")
        return
    filled = project._southbrook_backfill_defaults()
    if filled:
        _logger.info(
            "southbrook_project: project ID 1 backfilled with %s",
            ", ".join(filled))
    else:
        _logger.info(
            "southbrook_project: project ID 1 already populated, "
            "no backfill needed.")
