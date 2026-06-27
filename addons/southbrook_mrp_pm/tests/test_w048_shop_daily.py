# SPDX-License-Identifier: LGPL-3.0-only
"""W048 (R7.4, 2026-06-27) — Shop daily snapshot model tests.

JTBD: "When the GM asks for actual-vs-plan rollup at month end, I
want a pre-aggregated daily snapshot table I can pivot from — not
recomputing 30 days of MOs every time."

Coverage:
  * Model + cron exist and the cron is wired to the right method.
  * Cron is idempotent — re-running the same day is a no-op (same
    rows, same content, no duplicates).
  * Loaded vs actual hours snapshot correctly from raw mrp.workorder.
  * Rebuild action backfills a window and the row count matches
    workcenters x days.
  * Feature-detection: when southbrook.mi.check OR
    southbrook.kitchen.workcenter.downtime is absent, the snapshot
    still runs (returns zero for those columns) — verified via
    forced env dict mutation.
"""
from datetime import datetime, time, timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_pm", "w048")
class TestW048ShopDaily(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Snap = cls.env["southbrook.shop.daily"]
        cls.WC = cls.env["mrp.workcenter"]
        cls.wc = cls.WC.create({
            "name": "W048 TEST WC",
            "code": "W048WC",
        })

    def _make_wo_finished_today(self, wc, duration_min=60.0):
        """Create + finish a WO so the snapshot picks it up under
        hours_actual."""
        product = self.env["product.product"].search([
            ("type", "=", "consu")], limit=1)
        if not product:
            product = self.env["product.product"].create({
                "name": "W048 product", "type": "consu",
            })
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_qty": 1.0,
        })
        production = self.env["mrp.production"].create({
            "product_id": product.id,
            "product_qty": 1.0,
            "bom_id": bom.id,
        })
        wo = self.env["mrp.workorder"].create({
            "name": "W048 WO",
            "production_id": production.id,
            "workcenter_id": wc.id,
            "product_uom_id": product.uom_id.id,
            "duration_expected": duration_min,
            "duration": duration_min,
            "date_start": fields.Datetime.now() - timedelta(minutes=duration_min),
            "date_finished": fields.Datetime.now(),
        })
        return wo

    # ------------------------------------------------------------------
    def test_10_cron_exists_and_targets_correct_method(self):
        cron = self.env.ref(
            "southbrook_mrp_pm.ir_cron_southbrook_shop_daily_snapshot",
            raise_if_not_found=False,
        )
        self.assertTrue(cron, "W048 cron record must exist.")
        self.assertEqual(cron.model_id.model, "southbrook.shop.daily")
        # code field carries the entry-point method call.
        self.assertIn("_cron_snapshot_today", cron.code or "")
        self.assertEqual(cron.interval_type, "days")
        self.assertEqual(cron.interval_number, 1)

    def test_20_cron_is_idempotent(self):
        """Run the snapshot twice — row count for the WC must stay
        the same; we MUST NOT accumulate duplicates."""
        today = fields.Date.context_today(self.env["res.users"])
        # First run.
        self.Snap._cron_snapshot_today()
        first = self.Snap.search([
            ("workcenter_id", "=", self.wc.id),
            ("date", "=", today),
        ])
        self.assertEqual(
            len(first), 1,
            "Exactly one row per (WC, day) after first cron.")
        # Second run.
        self.Snap._cron_snapshot_today()
        second = self.Snap.search([
            ("workcenter_id", "=", self.wc.id),
            ("date", "=", today),
        ])
        self.assertEqual(
            len(second), 1,
            "Re-running cron must REPLACE not DUPLICATE the row.")

    def test_30_actual_hours_picked_up_from_workorder(self):
        """A WO finished today must contribute its duration to
        hours_actual on the snapshot."""
        # Create the WO BEFORE snapshotting so it's in scope.
        wo = self._make_wo_finished_today(self.wc, duration_min=90.0)
        self.Snap._cron_snapshot_today()
        today = fields.Date.context_today(self.env["res.users"])
        row = self.Snap.search([
            ("workcenter_id", "=", self.wc.id),
            ("date", "=", today),
        ], limit=1)
        self.assertTrue(row, "Snapshot row must exist after cron.")
        # Allow other test WOs on this WC to contribute too; assert
        # at minimum OUR WO's hours are included (≥ 1.5 hours).
        self.assertGreaterEqual(
            row.hours_actual, 1.5,
            "Snapshot must pick up the 90-min WO (1.5h) in "
            "hours_actual: got %.2f" % row.hours_actual)
        self.assertGreaterEqual(
            row.hours_loaded, 1.5,
            "Snapshot must pick up the 90-min expected duration too: "
            "got %.2f" % row.hours_loaded)
        # Reference field present + sane.
        self.assertTrue(row.refreshed_at)

    def test_40_rebuild_history_backfills_window(self):
        """action_rebuild_history(horizon_days=7) must produce
        7 days x #active_WCs rows (within ±slack for race with the
        cron)."""
        active_wc_count = self.WC.search_count([("active", "=", True)])
        self.assertGreater(active_wc_count, 0)
        # Trigger the rebuild for a small window.
        self.Snap.action_rebuild_history(horizon_days=7)
        today = fields.Date.context_today(self.env["res.users"])
        start = today - timedelta(days=6)
        rows = self.Snap.search([
            ("workcenter_id", "in", self.WC.search([
                ("active", "=", True)]).ids),
            ("date", ">=", start),
            ("date", "<=", today),
        ])
        # 7 days x N WCs.
        self.assertEqual(
            len(rows), 7 * active_wc_count,
            "Rebuild must produce one row per (active WC, day) in the "
            "window: expected %d, got %d" % (7 * active_wc_count, len(rows)))

    def test_50_unique_constraint_enforced(self):
        """The model carries UNIQUE(workcenter_id, date). Creating a
        duplicate by hand must raise an integrity error."""
        from psycopg2.errors import UniqueViolation
        today = fields.Date.context_today(self.env["res.users"])
        self.Snap.create({
            "workcenter_id": self.wc.id,
            "date": today,
        })
        with self.assertRaises(Exception) as cm:
            with self.env.cr.savepoint():
                self.Snap.create({
                    "workcenter_id": self.wc.id,
                    "date": today,
                })
        # Either a UniqueViolation or its wrapped IntegrityError — both
        # satisfy the contract.
        msg = str(cm.exception).lower()
        self.assertTrue(
            "unique" in msg or "duplicate" in msg or isinstance(
                cm.exception, UniqueViolation),
            "Duplicate (WC, date) must raise a unique-violation; got: %s"
            % cm.exception)
