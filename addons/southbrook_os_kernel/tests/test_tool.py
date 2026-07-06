# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook_os_kernel")
class TestOsTool(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tool = cls.env["southbrook.os.tool"]
        cls.active_tool = cls.Tool.create(
            {
                "name": "Active Test Tool",
                "code": "test_tool_active",
                "http_method": "GET",
                "path": "/test/active",
                "auth": "public",
                "description": "An active test tool.",
                "active": True,
            }
        )
        cls.inactive_tool = cls.Tool.create(
            {
                "name": "Inactive Test Tool",
                "code": "test_tool_inactive",
                "http_method": "POST",
                "path": "/test/inactive",
                "auth": "session",
                "description": "An inactive test tool.",
                "active": False,
            }
        )

    def test_manifest_shape(self):
        manifest = self.Tool.manifest()
        entry = next(
            (row for row in manifest if row["code"] == "test_tool_active"), None
        )
        self.assertIsNotNone(entry)
        self.assertEqual(
            set(entry.keys()), {"code", "method", "path", "auth", "description"}
        )
        self.assertEqual(entry["method"], "GET")
        self.assertEqual(entry["path"], "/test/active")
        self.assertEqual(entry["auth"], "public")

    def test_manifest_only_active(self):
        codes = [row["code"] for row in self.Tool.manifest()]
        self.assertIn("test_tool_active", codes)
        self.assertNotIn("test_tool_inactive", codes)

    def test_manifest_ordered_by_code(self):
        self.Tool.create(
            {
                "name": "A Test Tool",
                "code": "aaa_test_tool",
                "path": "/test/aaa",
            }
        )
        codes = [row["code"] for row in self.Tool.manifest()]
        self.assertEqual(codes, sorted(codes))
