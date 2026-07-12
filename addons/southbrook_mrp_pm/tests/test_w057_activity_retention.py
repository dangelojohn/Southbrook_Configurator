# SPDX-License-Identifier: LGPL-3.0-only
"""W057 (MFG-REVIEW-R7.6) — activity retention cron.

Contract:
  1. _sbk_purge_done_activities only deletes archived (done)
     activities older than the cutoff.
  2. It NEVER touches open (active=True) activities, regardless of
     their date_deadline.
  3. It NEVER touches recently-archived activities (within window).
"""
from datetime import date, timedelta

from odoo.tests import TransactionCase


class TestW057ActivityRetention(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Activity = self.env["mail.activity"]
        # Anchor activities on res.partner (always present, mail-enabled).
        self.partner = self.env["res.partner"].create({
            "name": "W057-test-anchor",
        })
        self.partner_model_id = self.env["ir.model"]._get_id("res.partner")
        self.act_type = self.env.ref("mail.mail_activity_data_todo")

    def _make_activity(self):
        return self.Activity.create({
            "res_model_id": self.partner_model_id,
            "res_id": self.partner.id,
            "activity_type_id": self.act_type.id,
            "summary": "W057 test",
            "date_deadline": date.today(),
        })

    def test_open_activity_never_purged(self):
        """active=True row must survive even with a 0-day cutoff."""
        open_act = self._make_activity()
        self.Activity._sbk_purge_done_activities(days=0)
        self.assertTrue(
            open_act.exists(),
            "W057: open activities must never be purged",
        )

    def test_recent_done_activity_not_purged(self):
        """Done but within retention window stays put."""
        done_act = self._make_activity()
        done_act._action_done()
        # date_done is today; cutoff is today - 90d. Stays.
        self.Activity._sbk_purge_done_activities(days=90)
        self.assertTrue(
            done_act.with_context(active_test=False).exists(),
            "W057: recently-done activities within window must survive",
        )

    def test_old_done_activity_purged(self):
        """Done + outside window -> gone."""
        old_act = self._make_activity()
        old_act._action_done()
        # date_done is a STORED COMPUTED field (@api.depends('active') —
        # archiving stamps it to now, but only when it is currently empty).
        # Flush the computed value to the DB FIRST, otherwise the SQL backdate
        # below is discarded: a later invalidate + read/search re-runs
        # _compute_date_done from scratch (reading date_done as empty
        # mid-compute) and resets it to today. Flushing persists it and clears
        # the pending-compute flag, so the SQL value survives.
        old_act.flush_recordset()
        # Force date_done to 100 days ago — bypass the compute.
        old_date = date.today() - timedelta(days=100)
        self.env.cr.execute(
            "UPDATE mail_activity SET date_done=%s WHERE id=%s",
            (old_date, old_act.id),
        )
        old_act.invalidate_recordset(["date_done"])
        count = self.Activity._sbk_purge_done_activities(days=90)
        self.assertGreaterEqual(
            count, 1,
            "W057: expected at least one old activity purged",
        )
        self.assertFalse(
            old_act.with_context(active_test=False).exists(),
            "W057: old done activity should be unlinked",
        )
