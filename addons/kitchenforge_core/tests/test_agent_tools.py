# SPDX-License-Identifier: LGPL-3.0-only
"""Smoke tests for the agent tool catalog (the JSON-Schema'd tool list)."""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.kitchenforge_core.controllers.agent_tools import TOOL_CATALOG


@tagged("post_install", "-at_install", "kitchenforge")
class TestAgentToolCatalog(TransactionCase):

    def test_catalog_has_core_tools(self):
        names = {t["name"] for t in TOOL_CATALOG}
        self.assertIn("instantiate", names)
        self.assertIn("add_zone", names)
        self.assertIn("confirm_quote", names)
        self.assertIn("release_mos", names)
        self.assertIn("raise_eco", names)

    def test_each_tool_has_required_keys(self):
        for tool in TOOL_CATALOG:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("input_schema", tool)
            self.assertIn("endpoint", tool)
            schema = tool["input_schema"]
            self.assertEqual(schema["type"], "object")
            self.assertIn("required", schema)
            self.assertIn("properties", schema)

    def test_instantiate_schema_shape(self):
        tool = next(t for t in TOOL_CATALOG if t["name"] == "instantiate")
        props = tool["input_schema"]["properties"]
        self.assertIn("template_id", props)
        self.assertIn("partner_id", props)
        self.assertEqual(props["template_id"]["type"], "integer")
        self.assertEqual(props["partner_id"]["type"], "integer")
