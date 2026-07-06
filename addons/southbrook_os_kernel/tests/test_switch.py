# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_os_kernel")
class TestOsSwitch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Switch = cls.env["southbrook.os.switch"]

    def test_is_on_default_when_absent(self):
        # No row at all for this key -> caller's default is returned as-is,
        # for both a falsy and a truthy default.
        self.assertFalse(self.Switch.is_on("os.ai.does_not_exist"))
        self.assertFalse(
            self.Switch.is_on("os.ai.does_not_exist", default=False)
        )
        self.assertTrue(
            self.Switch.is_on("os.ai.does_not_exist", default=True)
        )

    def test_set_switch_upsert(self):
        rec = self.Switch.set_switch("os.test.upsert", True, name="Test Upsert")
        self.assertTrue(rec.enabled)
        self.assertEqual(rec.key, "os.test.upsert")
        self.assertEqual(rec.name, "Test Upsert")
        self.assertTrue(self.Switch.is_on("os.test.upsert"))

        # Second call on the same key must update the existing row, not
        # create a duplicate (uniqueness is enforced via models.Constraint).
        rec2 = self.Switch.set_switch("os.test.upsert", False)
        self.assertEqual(rec.id, rec2.id)
        self.assertFalse(rec2.enabled)
        self.assertFalse(self.Switch.is_on("os.test.upsert"))
        count = self.Switch.search_count([("key", "=", "os.test.upsert")])
        self.assertEqual(count, 1)

    def test_disabled_blocks(self):
        self.Switch.set_switch("os.test.disabled", False, name="Disabled Switch")
        self.assertFalse(self.Switch.is_on("os.test.disabled", default=True))

    def test_is_on_never_raises_on_bad_input(self):
        # Defensive: even a clearly bogus key must not raise, it must fall
        # back to the caller's default.
        self.assertEqual(
            self.Switch.is_on(None, default="fallback"), "fallback"
        )
