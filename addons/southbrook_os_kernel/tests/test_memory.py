# SPDX-License-Identifier: LGPL-3.0-only
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_os_kernel")
class TestOsMemory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Memory = cls.env["southbrook.os.memory"]

    def test_remember_recall_roundtrip(self):
        self.Memory.remember("test_ns", "greeting", {"hello": "world"})
        value = self.Memory.recall("test_ns", "greeting")
        self.assertEqual(value, {"hello": "world"})

    def test_recall_missing_returns_default(self):
        value = self.Memory.recall("test_ns", "does_not_exist", default="fallback")
        self.assertEqual(value, "fallback")

    def test_recall_never_raises_on_missing(self):
        # No default provided -> None, no exception.
        value = self.Memory.recall("nope", "nope")
        self.assertIsNone(value)

    def test_remember_upsert(self):
        self.Memory.remember("test_ns", "counter", 1)
        self.Memory.remember("test_ns", "counter", 2)
        self.assertEqual(self.Memory.recall("test_ns", "counter"), 2)
        count = self.Memory.with_context(active_test=False).search_count(
            [("namespace", "=", "test_ns"), ("key", "=", "counter")]
        )
        self.assertEqual(count, 1, "remember must upsert, not duplicate")

    def test_ttl_expiry_falls_through_to_default(self):
        self.Memory.remember("test_ns", "expiring", "should_be_gone", ttl_hours=1)
        rec = self.Memory.with_context(active_test=False).search(
            [("namespace", "=", "test_ns"), ("key", "=", "expiring")], limit=1
        )
        # Force expiry by writing expires_at in the past directly (no sleep).
        rec.write({"expires_at": fields.Datetime.now() - timedelta(hours=2)})
        value = self.Memory.recall("test_ns", "expiring", default="gone")
        self.assertEqual(value, "gone")

    def test_vacuum_expired_removes_rows(self):
        self.Memory.remember("test_ns", "to_vacuum", "x")
        rec = self.Memory.with_context(active_test=False).search(
            [("namespace", "=", "test_ns"), ("key", "=", "to_vacuum")], limit=1
        )
        rec.write({"expires_at": fields.Datetime.now() - timedelta(hours=2)})
        self.Memory.vacuum_expired()
        remaining = self.Memory.with_context(active_test=False).search_count(
            [("namespace", "=", "test_ns"), ("key", "=", "to_vacuum")]
        )
        self.assertEqual(remaining, 0)

    def test_recall_corrupt_json_returns_default(self):
        self.Memory.remember("test_ns", "corrupt", "fine")
        rec = self.Memory.with_context(active_test=False).search(
            [("namespace", "=", "test_ns"), ("key", "=", "corrupt")], limit=1
        )
        rec.write({"value_json": "{not valid json"})
        value = self.Memory.recall("test_ns", "corrupt", default="safe")
        self.assertEqual(value, "safe")
