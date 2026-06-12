# SPDX-License-Identifier: LGPL-3.0-only
"""Post-install hook — backfill blank fields on project ID 1.

We can't use a data XML record because project ID 1 (the live "Test"
project) was created in the UI and has no xmlid. Doing a write via
the post_init_hook keeps the operation idempotent (we only fill
blanks; we never stomp values the operator already set).
"""
import logging
from datetime import date
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


def post_init_backfill_project_1(env):
    """Populate description, dates, and feature flags on project ID 1
    when those fields are blank. Idempotent — re-running the install
    won't overwrite values the operator already typed."""
    Project = env["project.project"]
    project = Project.browse(1).exists()
    if project:
        vals = {}

        if not project.description:
            vals["description"] = (
                "<p>Southbrook Cabinetry production tracking. Each task "
                "represents a single cabinet job moving through the "
                "five-stage pipeline: Design &amp; Quote → Cutting &amp; "
                "Machining → Assembly → Finishing → Delivery &amp; "
                "Install.</p>"
                "<p>Tag tasks with Rush / Custom / Warranty / Repair plus "
                "the scope (Kitchen / Vanity) so the Tasks Analysis report "
                "can slice the queue by priority and scope.</p>"
            )

        today = date.today()
        if not project.date_start:
            vals["date_start"] = today
        if not project.date:
            vals["date"] = today + relativedelta(months=6)

        # Tier 3: flip the two flags the QA pass flagged as most useful
        # for an ordered production flow. If the operator has manually
        # turned them off, we don't re-enable — they made that call.
        if not project.allow_task_dependencies:
            vals["allow_task_dependencies"] = True
        if not project.allow_milestones:
            vals["allow_milestones"] = True

        if vals:
            project.write(vals)
            _logger.info(
                "southbrook_project: project ID 1 backfilled with %s",
                ", ".join(vals.keys()),
            )
        else:
            _logger.info(
                "southbrook_project: project ID 1 already populated, "
                "no backfill needed.")
    else:
        _logger.info(
            "southbrook_project: project ID 1 not present, skipping "
            "post-init backfill (this is fine on a fresh DB).")

    tasks = env["project.task"].sudo().search([])
    if tasks:
        tasks.action_southbrook_refresh_mrp_readiness_snapshot()
        _logger.info(
            "southbrook_project: refreshed %s MRP readiness snapshots",
            len(tasks),
        )
    else:
        _logger.info("southbrook_project: no task readiness snapshots to refresh")
