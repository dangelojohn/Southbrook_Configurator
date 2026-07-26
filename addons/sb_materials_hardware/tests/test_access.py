# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestAccess(TransactionCase):
    def setUp(self):
        super().setUp()
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.env["product.template"].create({
            "name": "TEST Visible screw",
            "x_southbrook_tool_category_id": self.cat.id,
        })
        self.plain_user = self.env["res.users"].create({
            "name": "Catalog Reader",
            "login": "catalog_reader_test",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("southbrook_mrp_kitchen_tools.group_tool_operator").id,
            ])],
        })

    def test_internal_user_can_read_catalog(self):
        payload = self.env["materials.catalog.provider"].with_user(
            self.plain_user).get_catalog(scope="tools", category_id=self.cat.id)
        self.assertTrue(payload["ok"])
        self.assertIn("TEST Visible screw",
                      {r["name"] for r in payload["rows"]})

    def test_provider_source_contains_no_sudo(self):
        """The catalog must never elevate to read records."""
        import inspect
        from odoo.addons.sb_materials_hardware.models import (
            tools_catalog_provider, catalog_provider)
        for module in (tools_catalog_provider, catalog_provider):
            source = inspect.getsource(module)
            self.assertNotIn(".sudo()", source)
