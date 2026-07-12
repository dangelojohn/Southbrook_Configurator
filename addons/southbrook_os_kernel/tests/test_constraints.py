# SPDX-License-Identifier: LGPL-3.0-only
"""Direct enforcement tests for the four ``models.Constraint`` uniqueness
rules. The existing suite only proves the *helper methods* (set_switch,
remember) avoid duplicates via search-then-upsert — it never provokes a raw
duplicate create() that requires the SQL constraint itself to fire. Since
``models.Constraint`` replacing the silently-ignored v19 ``_sql_constraints``
is the single riskiest migration pattern in the module, a typo in a
constraint's SQL (e.g. a wrong column name) would otherwise ship undetected.
Each test forces a genuine duplicate INSERT and asserts the DB rejects it.
"""
from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "southbrook_os_kernel")
class TestOsKernelConstraints(TransactionCase):

    @mute_logger("odoo.sql_db")
    def test_switch_key_unique(self):
        Switch = self.env["southbrook.os.switch"]
        Switch.create({"key": "os.dup.switch", "name": "first"})
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                Switch.create({"key": "os.dup.switch", "name": "second"})
                self.env.flush_all()

    @mute_logger("odoo.sql_db")
    def test_memory_namespace_key_unique(self):
        Memory = self.env["southbrook.os.memory"]
        Memory.create({"namespace": "ns", "key": "dup"})
        # Same (namespace, key) must be rejected...
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                Memory.create({"namespace": "ns", "key": "dup"})
                self.env.flush_all()

    def test_memory_same_key_different_namespace_allowed(self):
        # ...but the SAME key under a DIFFERENT namespace must be allowed
        # (constraint is composite, not on key alone).
        Memory = self.env["southbrook.os.memory"]
        Memory.create({"namespace": "ns_a", "key": "shared"})
        rec = Memory.create({"namespace": "ns_b", "key": "shared"})
        self.assertTrue(rec.id)

    @mute_logger("odoo.sql_db")
    def test_agent_code_unique(self):
        Agent = self.env["southbrook.os.agent"]
        Agent.create({"name": "A", "code": "dup_agent"})
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                Agent.create({"name": "B", "code": "dup_agent"})
                self.env.flush_all()

    @mute_logger("odoo.sql_db")
    def test_tool_code_unique(self):
        Tool = self.env["southbrook.os.tool"]
        Tool.create({"name": "T1", "code": "dup_tool", "path": "/a"})
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                Tool.create({"name": "T2", "code": "dup_tool", "path": "/b"})
                self.env.flush_all()
