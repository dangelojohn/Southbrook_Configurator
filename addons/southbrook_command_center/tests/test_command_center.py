# SPDX-License-Identifier: LGPL-3.0-only
from odoo.exceptions import ValidationError
import json

from odoo.tests import HttpCase, TransactionCase, tagged
from psycopg2 import IntegrityError
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "southbrook_command_center")
class TestCommandException(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Exc = cls.env["southbrook.command.exception"]
        cls.Center = cls.env["southbrook.command.center"]
        cls.owner = cls.env.ref("base.user_admin")

    def _make(self, **kw):
        vals = {
            "exception_type": "mi_blocker",
            "source_model": "southbrook.mi.check",
            "source_res_id": 1,
            "severity": "critical",
            "severity_rank": 0,
            "owner_id": self.owner.id,
            "impact_summary": "Test blocker",
        }
        vals.update(kw)
        return self.Exc.create(vals)

    def test_create_and_name(self):
        rec = self._make()
        self.assertTrue(rec.name, "name must be auto-populated")
        self.assertEqual(rec.state, "new")

    def test_owner_required(self):
        with self.assertRaises(Exception):
            self.Exc.create({
                "exception_type": "mi_blocker",
                "source_model": "southbrook.mi.check",
                "source_res_id": 99,
                # no owner_id -> required violation
            })

    @mute_logger("odoo.sql_db")
    def test_source_uniqueness(self):
        self._make(source_res_id=42)
        with self.assertRaises(IntegrityError):
            self._make(source_res_id=42)

    def test_ack_resolve_transitions(self):
        rec = self._make(source_res_id=7)
        rec.action_acknowledge()
        self.assertEqual(rec.state, "acknowledged")
        self.assertTrue(rec.acknowledged_date)
        rec.action_resolve()
        self.assertEqual(rec.state, "resolved")
        self.assertTrue(rec.resolved_date)
        self.assertFalse(rec.active)

    def test_dismiss(self):
        rec = self._make(source_res_id=8)
        rec.action_dismiss()
        self.assertEqual(rec.state, "dismissed")
        self.assertFalse(rec.active)
        self.assertTrue(rec.dismissed_date, "dismiss stamps dismissed_date")
        self.assertFalse(rec.resolved_date,
                         "New->Dismissed must NOT set resolved_date")

    def test_reopen_undo(self):
        # action_reopen powers the dashboard undo-toast: a resolved/dismissed
        # exception returns to the open queue with timestamps cleared.
        rec = self._make(source_res_id=9)
        rec.action_resolve()
        self.assertEqual(rec.state, "resolved")
        self.assertFalse(rec.active)
        rec.action_reopen()
        self.assertEqual(rec.state, "new")
        self.assertTrue(rec.active)
        self.assertFalse(rec.resolved_date)
        # a dismissed one reopens too
        rec2 = self._make(source_res_id=10)
        rec2.action_dismiss()
        rec2.action_reopen()
        self.assertEqual(rec2.state, "new")
        self.assertTrue(rec2.active)

    # -- scoring: must return the contract dict and never raise ---------
    def test_factory_health_shape(self):
        out = self.Center.factory_health_score()
        for key in ("score", "band", "factors", "explanation"):
            self.assertIn(key, out)

    def test_schedule_confidence_shape(self):
        task = self.env["project.task"].search([], limit=1)
        out = self.Center.schedule_confidence(task)
        self.assertIn("band", out)
        self.assertIn("score", out)

    def test_job_margin_shape(self):
        task = self.env["project.task"].search([], limit=1)
        out = self.Center.job_margin(task)
        self.assertIn("band", out)

    def test_po_delivery_risk_shape(self):
        po = self.env["purchase.order"].search([], limit=1)
        out = self.Center.po_delivery_risk(po)
        self.assertIn("band", out)

    # -- materializer: idempotent, writes only its own model ------------
    def test_materialize_idempotent(self):
        # Two scans must not create duplicate exceptions for the same source.
        self.Exc._scan_and_materialize()
        before = self.Exc.with_context(active_test=False).search_count([])
        self.Exc._scan_and_materialize()
        after = self.Exc.with_context(active_test=False).search_count([])
        self.assertEqual(before, after, "re-scan must upsert, not duplicate")


@tagged("post_install", "-at_install", "southbrook_command_center")
class TestCommandCenterAuth(HttpCase):
    """The bootstrap route serves factory-health/flow and (via
    get_or_create_today) writes the exec snapshot — it must reject callers who
    are not internal Central Command members (regression for the missing route
    group gate)."""

    def _bootstrap(self):
        return self.url_open(
            "/command_center/bootstrap",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": {}}),
            headers={"Content-Type": "application/json"},
        )

    def test_non_member_is_forbidden(self):
        self.env["res.users"].create({
            "name": "CC Plain User",
            "login": "cc_plain_user",
            "password": "cc_plain_user",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.authenticate("cc_plain_user", "cc_plain_user")
        resp = self._bootstrap()
        body = json.loads(resp.text)
        # jsonrpc surfaces the AccessError as an error envelope (no result).
        self.assertIn("error", body)
        self.assertNotIn("result", body)

    def test_cc_member_is_allowed(self):
        self.env["res.users"].create({
            "name": "CC Member",
            "login": "cc_member",
            "password": "cc_member",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref(
                    "southbrook_command_center.group_command_center_user").id,
            ])],
        })
        self.authenticate("cc_member", "cc_member")
        resp = self._bootstrap()
        body = json.loads(resp.text)
        self.assertIn("result", body)
        self.assertIn("factory_health", body["result"])
