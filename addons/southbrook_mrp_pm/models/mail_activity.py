# SPDX-License-Identifier: LGPL-3.0-only
"""W057 (MFG-REVIEW-R7.6) — activity feed retention.

mail.activity rows pile up on a manufacturing floor (every WO check,
every NCR, every breakdown spawns activities) and per the R7
supplementary the growth pattern accelerates mid-year. Untrimmed the
table balloons past 10M+ rows and the activity widget queries
(user_id + date_deadline scans) tank.

We trim only DONE activities older than N days. Open activities
(date_done IS NULL) are someones live to-do — never touch them.
Chatter messages (mail.message) carry the durable record of what
was done, so deleting the completed activity row loses no audit
information.

Wired via data/activity_retention_cron.xml — runs daily.
"""
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import config


_logger = logging.getLogger(__name__)


class MailActivity(models.Model):
    _inherit = "mail.activity"

    @api.model
    def _sbk_purge_done_activities(self, days=90):
        """Delete completed mail.activity rows older than `days`
        (default 90). Returns the count deleted for logging.

        v19 semantics: completing an activity calls `action_archive()`
        AND `_compute_date_done` stamps `date_done` to now. So
        "completed" = `active=False` AND `date_done != False`.

        We must search with `active_test=False` because the default
        ir_rule filters archived records out.

        Bounded by:
          * active = False (archived = done)
          * date_done < today - days
        Never touches open (active=True) activities. Safe to run daily.
        """
        cutoff = fields.Date.today() - relativedelta(days=days)
        domain = [
            ("active", "=", False),
            ("date_done", "!=", False),
            ("date_done", "<", cutoff),
        ]
        # Batched delete: the motivating scenario (per this module's docstring)
        # is a table that has ballooned past 10M+ rows. Searching + unlinking
        # the whole backlog in one shot would load it all into memory and hold
        # one giant lock/transaction (OOM / replication lag / rollback-wedge on
        # failure). Delete in bounded chunks, committing between them so each
        # batch releases its locks and a mid-run failure keeps the progress
        # already made. (TestCursor.commit is a savepoint, so this is test-safe.)
        batch = 1000
        count = 0
        while True:
            old = self.with_context(active_test=False).search(domain, limit=batch)
            if not old:
                break
            n = len(old)
            old.unlink()
            count += n
            # Commit between batches in production so each chunk releases its
            # locks and a mid-run failure keeps the progress already made. The
            # search(limit) loop already bounds MEMORY; the commit bounds
            # transaction/lock size. Skipped under --test-enable, where the
            # TestCursor forbids commit (it would break test rollback).
            if not config["test_enable"]:
                self.env.cr.commit()
            if n < batch:
                break
        _logger.info(
            "W057 activity retention: trimmed %d done activities "
            "older than %d days",
            count, days,
        )
        return count
