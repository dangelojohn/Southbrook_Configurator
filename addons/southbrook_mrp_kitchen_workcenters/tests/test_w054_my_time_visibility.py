# SPDX-License-Identifier: LGPL-3.0-only
"""W054 (R2.12) — Operator-visible time tracking on WO form.

`mrp.workorder.x_sbk_my_time_ids` and `x_sbk_my_time_today_min` are
@api.depends_context('uid') computes that surface each viewer's own
`mrp.workcenter.productivity` rows for a WO, NEVER another operator's.

Tests verify:
  * x_sbk_my_time_ids returns only the current user's rows
  * a second user reading the same WO sees their own rows only
  * x_sbk_my_time_today_min sums duration for today + current user
  * yesterday's rows are excluded from x_sbk_my_time_today_min
"""
from datetime import datetime, time as dtime, timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w054")
class TestW054MyTimeVisibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Workorder = cls.env["mrp.workorder"]
        cls.Productivity = cls.env["mrp.workcenter.productivity"]
        # Both users need MRP-user access to read work orders; without a group
        # a bare user can't read mrp.workorder at all, so the "my time" compute
        # (which reads the WO) raised AccessError in the no-logs case (with
        # logs, the productivity link granted implicit access and masked it).
        mrp_group = cls.env.ref("mrp.group_mrp_user")
        cls.user_a = cls.env["res.users"].create({
            "name": "W054 User A",
            "login": "w054_a@test",
            "email": "w054_a@test",
            "group_ids": [(4, mrp_group.id)],
        })
        cls.user_b = cls.env["res.users"].create({
            "name": "W054 User B",
            "login": "w054_b@test",
            "email": "w054_b@test",
            "group_ids": [(4, mrp_group.id)],
        })
        wc = cls.env["mrp.workcenter"].search([], limit=1)
        if not wc:
            wc = cls.env["mrp.workcenter"].create({
                "name": "W054 WC", "code": "W054WC",
            })
        cls.wc = wc
        product = cls.env["product.product"].search([
            ("type", "=", "consu")], limit=1)
        if not product:
            product = cls.env["product.product"].create({
                "name": "W054 product", "type": "consu",
            })
        bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        production = cls.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        cls.wo = cls.Workorder.create({
            "name": "W054 WO",
            "production_id": production.id,
            "workcenter_id": wc.id,
            "product_uom_id": product.uom_id.id,
        })
        # Default productivity loss reason for the rows.
        cls.loss = cls.env["mrp.workcenter.productivity.loss"].search([
            ("loss_type", "=", "productive")], limit=1)
        if not cls.loss:
            # Bootstrap a productive loss row for the test sandbox.
            cls.loss = cls.env["mrp.workcenter.productivity.loss"].create({
                "name": "W054 productive",
                "loss_type": "productive",
            })

    def _log_time(self, user, start, end):
        return self.Productivity.create({
            "workcenter_id": self.wc.id,
            "workorder_id": self.wo.id,
            "user_id": user.id,
            "loss_id": self.loss.id,
            "date_start": start,
            "date_end": end,
        })

    def test_10_my_time_ids_returns_only_current_user(self):
        """User A reading the WO sees A's rows, NOT B's."""
        today_morning = datetime.combine(
            fields.Date.context_today(self.env.user), dtime(8, 0))
        self._log_time(self.user_a, today_morning,
                       today_morning + timedelta(minutes=30))
        self._log_time(self.user_b, today_morning,
                       today_morning + timedelta(minutes=45))
        # Read as user_a.
        wo_a = self.wo.with_user(self.user_a)
        my_a = wo_a.x_sbk_my_time_ids
        self.assertEqual(len(my_a), 1,
                         "User A should see exactly their 1 row")
        self.assertEqual(my_a.user_id, self.user_a)
        # Read as user_b — different filter result.
        wo_b = self.wo.with_user(self.user_b)
        my_b = wo_b.x_sbk_my_time_ids
        self.assertEqual(len(my_b), 1,
                         "User B should see exactly their 1 row")
        self.assertEqual(my_b.user_id, self.user_b)

    def test_20_my_time_today_min_sums_only_today_current_user(self):
        """Sum excludes other users AND excludes yesterday's rows."""
        today_morning = datetime.combine(
            fields.Date.context_today(self.env.user), dtime(8, 0))
        yesterday_morning = today_morning - timedelta(days=1)
        # User A: 30 min today + 60 min yesterday
        self._log_time(self.user_a, today_morning,
                       today_morning + timedelta(minutes=30))
        self._log_time(self.user_a, yesterday_morning,
                       yesterday_morning + timedelta(minutes=60))
        # User B: 99 min today (must NOT count toward A's total)
        self._log_time(self.user_b, today_morning,
                       today_morning + timedelta(minutes=99))
        # Force a recompute under user_a's lens.
        wo_a = self.wo.with_user(self.user_a)
        wo_a.invalidate_recordset(
            fnames=["x_sbk_my_time_today_min", "x_sbk_my_time_ids"])
        self.assertAlmostEqual(
            wo_a.x_sbk_my_time_today_min, 30.0, places=1,
            msg="user_a's today total should be exactly 30 min")

    def test_30_empty_when_no_logs(self):
        wo_a = self.wo.with_user(self.user_a)
        wo_a.invalidate_recordset(
            fnames=["x_sbk_my_time_today_min", "x_sbk_my_time_ids"])
        self.assertFalse(wo_a.x_sbk_my_time_ids)
        self.assertAlmostEqual(
            wo_a.x_sbk_my_time_today_min, 0.0, places=1)
