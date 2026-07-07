# SPDX-License-Identifier: LGPL-3.0-only
"""P0 alerting spine — do not blast the pre-existing backlog.

When the email-digest cron (19.0.1.1.0) goes live there are already
hundreds of open high/critical exceptions materialized (a symptom of the
stalled plant the E2E review found). Emailing all of them on the first run
would be noise, not signal. Mark every pre-existing exception as already
notified so the digest only pushes genuinely NEW issues from here forward.

Runs post-load, after the ORM has added the alert_notified column.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE southbrook_command_exception
           SET alert_notified = TRUE,
               alert_notified_date = COALESCE(alert_notified_date, now() AT TIME ZONE 'UTC')
         WHERE alert_notified IS NOT TRUE
        """
    )
