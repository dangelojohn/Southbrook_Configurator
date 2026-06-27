# SPDX-License-Identifier: LGPL-3.0-only
"""W069 (R3.14, 2026-06-27) — Downtime → reschedule listener tests.

JTBD: When a workcenter goes down, the planner should be notified at
downtime time, not when the kanban turns red.

Coverage:
  * Active-on-create downtime fires the listener and posts a chatter
    message on every overlapping WO at that WC.
  * Overlapping WO in 'ready' or 'progress' state gets the W069 tag.
  * Non-overlapping WO (window outside downtime) gets NOTHING.
  * Idempotency: re-firing the listener on the same downtime + WO
    does not double-post (chatter tag dedupe).
  * No auto-reschedule: WO date_start / date_finished are unchanged
    after the listener runs.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w069")
class TestW069DowntimeNotify(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Downtime = cls.env["southbrook.kitchen.workcenter.downtime"]
        cls.WC = cls.env["mrp.workcenter"]
        cls.Workorder = cls.env["mrp.workorder"]
        cls.Production = cls.env["mrp.production"]

        cls.wc = cls.WC.create({
            "name": "W069 TEST WC",
            "code": "W069WC",
        })
        cls.product = cls.env["product.product"].create({
            "name": "W069 product",
            "type": "consu",
        })
        cls.bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        cls.mo = cls.Production.create({
            "product_id": cls.product.id,
            "product_qty": 1.0,
            "bom_id": cls.bom.id,
        })

    def _make_wo(self, wc, date_start, date_finished, state="ready"):
        wo = self.Workorder.create({
            "name": "W069 WO",
            "production_id": self.mo.id,
            "workcenter_id": wc.id,
            "product_uom_id": self.product.uom_id.id,
            "duration_expected": 60.0,
            "date_start": date_start,
            "date_finished": date_finished,
        })
        # Force state directly — bypass MRP state machine to keep the
        # test focused on the W069 listener (the listener filters on
        # state in ('ready','progress')).
        wo.state = state
        return wo

    def _make_active_downtime(self, wc, start, end, reason="machine_breakdown"):
        return self.Downtime.create({
            "name": "W069 test downtime",
            "workcenter_id": wc.id,
            "date_start": start,
            "date_end": end,
            "state": "active",
            "reason": reason,
        })

    # ------------------------------------------------------------------
    def test_10_overlapping_wo_gets_w069_chatter(self):
        """A 'ready' WO whose window overlaps the downtime must receive
        a chatter message tagged with the downtime id."""
        now = fields.Datetime.now()
        wo = self._make_wo(
            self.wc,
            date_start=now,
            date_finished=now + timedelta(hours=2),
            state="ready",
        )
        dt = self._make_active_downtime(
            self.wc,
            start=now + timedelta(minutes=30),
            end=now + timedelta(minutes=90),
        )
        tag = "[W069:dt=%d]" % dt.id
        bodies = " ".join((wo.message_ids.mapped("body") or []))
        self.assertIn(
            tag, bodies,
            "W069: overlapping WO must receive a chatter message "
            "tagged with the downtime id.",
        )

    def test_20_non_overlapping_wo_gets_nothing(self):
        """A WO whose window does NOT overlap the downtime must NOT
        receive the W069 chatter tag."""
        now = fields.Datetime.now()
        wo = self._make_wo(
            self.wc,
            date_start=now + timedelta(hours=10),
            date_finished=now + timedelta(hours=12),
            state="ready",
        )
        dt = self._make_active_downtime(
            self.wc,
            start=now,
            end=now + timedelta(hours=1),
        )
        tag = "[W069:dt=%d]" % dt.id
        bodies = " ".join((wo.message_ids.mapped("body") or []))
        self.assertNotIn(
            tag, bodies,
            "W069: non-overlapping WO must NOT receive a W069 chatter.",
        )

    def test_30_idempotent_no_double_post(self):
        """Re-firing the listener on the same downtime + WO MUST NOT
        double-post the same chatter line."""
        now = fields.Datetime.now()
        wo = self._make_wo(
            self.wc,
            date_start=now,
            date_finished=now + timedelta(hours=2),
            state="progress",
        )
        dt = self._make_active_downtime(
            self.wc,
            start=now,
            end=now + timedelta(hours=1),
        )
        tag = "[W069:dt=%d]" % dt.id
        first_count = sum(
            1 for b in wo.message_ids.mapped("body") if b and tag in b)
        self.assertGreaterEqual(first_count, 1)
        # Re-fire the listener explicitly.
        dt._w069_notify_planner_of_affected_wos()
        second_count = sum(
            1 for b in wo.message_ids.mapped("body") if b and tag in b)
        self.assertEqual(
            first_count, second_count,
            "W069: re-firing on the same downtime must not double-post "
            "(got %d -> %d)." % (first_count, second_count),
        )

    def test_40_no_auto_reschedule(self):
        """The listener must NEVER move WO date_start/date_finished."""
        now = fields.Datetime.now()
        original_start = now
        original_end = now + timedelta(hours=2)
        wo = self._make_wo(
            self.wc,
            date_start=original_start,
            date_finished=original_end,
            state="ready",
        )
        self._make_active_downtime(
            self.wc,
            start=now + timedelta(minutes=30),
            end=now + timedelta(minutes=90),
        )
        # Compare seconds (Odoo strips microseconds on Datetime).
        self.assertEqual(
            wo.date_start.replace(microsecond=0),
            original_start.replace(microsecond=0),
            "W069: WO date_start must NOT be moved by the listener.",
        )
        self.assertEqual(
            wo.date_finished.replace(microsecond=0),
            original_end.replace(microsecond=0),
            "W069: WO date_finished must NOT be moved by the listener.",
        )
