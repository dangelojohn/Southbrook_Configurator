# SPDX-License-Identifier: LGPL-3.0-only
"""Ledger tests: caller provenance and retention pruning.

* Provenance — the ledger row is created via sudo() (to bypass the admin-only
  create ACL), so without an explicit user_id it would record SUPERUSER on
  every call and lose per-user cost attribution. run() must stamp the REAL
  caller.
* Retention — the ledger grows one row per call with no natural bound;
  autovacuum() must prune rows past os.ai.ledger_retention_days and honour the
  <= 0 "keep forever" opt-out.
"""
from datetime import timedelta

from odoo import fields, SUPERUSER_ID
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_os_kernel")
class TestOsLedger(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Switch = cls.env["southbrook.os.switch"]
        cls.Kernel = cls.env["southbrook.os.ai.kernel"]
        cls.Request = cls.env["southbrook.os.ai.request"]
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.ICP.set_param("os.ai.transport", "mock")
        cls.Switch.set_switch("os.ai.enabled", True, name="AI Kernel - master")
        cls.messages = [{"role": "user", "content": "hello"}]

    def test_ledger_records_real_caller_not_superuser(self):
        # TransactionCase itself runs as SUPERUSER, so drive run() as a genuine
        # non-superuser internal user. Despite the ledger row being written via
        # sudo(), user_id must be that caller — never OdooBot/SUPERUSER — which
        # is what makes per-user cost attribution possible.
        caller = self.env["res.users"].create({
            "name": "Kernel Caller",
            "login": "kernel_caller_test",
            # v19: res.users.groups_id was renamed to group_ids.
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.assertNotEqual(caller.id, SUPERUSER_ID)
        out = self.Kernel.with_user(caller).run("smoke_test", self.messages)
        self.assertTrue(out["ok"])
        row = self.Request.browse(out["request_id"])
        self.assertEqual(row.user_id, caller)
        self.assertNotEqual(row.user_id.id, SUPERUSER_ID)

    def _make_row(self, feature="prune_me"):
        return self.Request.create({"feature": feature, "state": "done"})

    def _backdate(self, row, days):
        # create_date is auto-managed; backdate it directly in SQL, then drop
        # the ORM cache so the model re-reads the persisted value.
        old = fields.Datetime.now() - timedelta(days=days)
        self.env.cr.execute(
            "UPDATE southbrook_os_ai_request SET create_date = %s WHERE id = %s",
            (old, row.id),
        )
        row.invalidate_recordset(["create_date"])

    def test_autovacuum_prunes_old_rows(self):
        self.ICP.set_param("os.ai.ledger_retention_days", "1")
        old_row = self._make_row("old")
        fresh_row = self._make_row("fresh")
        self._backdate(old_row, days=3)
        pruned = self.Request.autovacuum()
        self.assertGreaterEqual(pruned, 1)
        self.assertFalse(old_row.exists(), "row past retention must be pruned")
        self.assertTrue(fresh_row.exists(), "recent row must be kept")

    def test_autovacuum_zero_retention_keeps_everything(self):
        self.ICP.set_param("os.ai.ledger_retention_days", "0")
        old_row = self._make_row("keep_forever")
        self._backdate(old_row, days=9999)
        pruned = self.Request.autovacuum()
        self.assertEqual(pruned, 0)
        self.assertTrue(old_row.exists(), "retention <= 0 must keep all rows")
