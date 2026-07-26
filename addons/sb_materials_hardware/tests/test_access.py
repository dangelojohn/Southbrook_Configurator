# SPDX-License-Identifier: LGPL-3.0-only
import re
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

    def test_get_detail_without_operator_group_is_denied(self):
        """get_catalog's access gate is incidental: it only fires because
        _build_payload always calls _categories(), which touches
        southbrook.tool.category. _build_detail reaches that model only
        via _columns(category), which short-circuits when category is
        falsy — so a product with NO category set let a base.group_user
        -only account read get_detail() with no gate at all.
        Use a product with no category to hit exactly that gap.
        """
        uncategorized = self.env["product.template"].create({
            "name": "TEST Uncategorized Widget",
        })
        no_access_user = self.env["res.users"].create({
            "name": "No Catalog Access",
            "login": "no_catalog_access_test",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        detail = self.env["materials.catalog.provider"].with_user(
            no_access_user).get_detail(
                uncategorized.product_variant_ids[0].id)
        self.assertFalse(detail["ok"])

    def test_provider_source_contains_no_sudo(self):
        """The catalog must never elevate to read records.

        This check catches the substring '.sudo(' preceded by a dot, with
        optional whitespace between the dot and opening paren. It catches
        common forms like .sudo(), .sudo(user), and .sudo (with space).

        Does NOT catch:
        - Aliased or dynamically-constructed calls (e.g., via variable ref)
        - Comments that happen to contain the text
        """
        import inspect
        from odoo.addons.sb_materials_hardware.models import (
            tools_catalog_provider, catalog_provider)
        sudo_pattern = re.compile(r"\.sudo\s*\(")
        for module in (tools_catalog_provider, catalog_provider):
            source = inspect.getsource(module)
            self.assertIsNone(
                sudo_pattern.search(source),
                f"Found .sudo() call in {module.__name__}"
            )
