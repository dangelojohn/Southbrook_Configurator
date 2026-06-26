# SPDX-License-Identifier: LGPL-3.0-only
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMcpTool(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tool = cls.env["southbrook.integrations.mcp_tool"]
        cls.Partner = cls.env["res.partner"]
        cls.model_partner = cls.env["ir.model"].search(
            [("model", "=", "res.partner")], limit=1)
        # Seed two partners so domain filtering can be tested.
        cls.alice = cls.Partner.create({"name": "MCP Alice"})
        cls.bob = cls.Partner.create({"name": "MCP Bob"})

    def _make_tool(self, **overrides):
        defaults = {
            "name": "test_partner_list",
            "category": "read",
            "model_id": self.model_partner.id,
            "domain_json": '[["name", "=", "MCP Alice"]]',
            "read_fields_json": '["name"]',
            "enabled": True,
        }
        defaults.update(overrides)
        return self.Tool.create(defaults)

    def test_invoke_respects_domain(self):
        tool = self._make_tool()
        result = tool.invoke("{}")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["rows"][0]["name"], "MCP Alice")

    def test_invoke_only_returns_listed_fields(self):
        tool = self._make_tool()
        result = tool.invoke("{}")
        row = result["rows"][0]
        # Only id + listed fields come back.
        self.assertIn("name", row)
        self.assertIn("id", row)
        self.assertNotIn("email", row)
        self.assertNotIn("phone", row)

    def test_disabled_tool_returns_403(self):
        tool = self._make_tool(name="disabled_one", enabled=False)
        with self.assertRaises(AccessError):
            tool.invoke("{}")

    def test_write_category_blocked_in_v1(self):
        tool = self._make_tool(name="write_one", category="write")
        with self.assertRaises(AccessError):
            tool.invoke("{}")

    def test_unknown_field_raises_user_error(self):
        tool = self._make_tool(
            name="bad_field",
            read_fields_json='["not_a_field_xyz"]',
        )
        with self.assertRaises(UserError):
            tool.invoke("{}")

    def test_invalid_domain_raises_user_error(self):
        tool = self._make_tool(
            name="bad_dom", domain_json='{"not": "a list"}')
        with self.assertRaises(UserError):
            tool.invoke("{}")
