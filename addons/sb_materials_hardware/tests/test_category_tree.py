# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestCategoryTree(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat_screws = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.cat_conf = self.env.ref(
            "southbrook_mrp_kitchen_tools.cat_screw_confirmat")
        self.tmpl = self.env["product.template"].create({
            "name": "TEST Confirmat 7x50",
            "x_southbrook_tool_category_id": self.cat_conf.id,
        })

    def _cats(self):
        payload = self.Provider.get_catalog(scope="tools")
        return {c["id"]: c for c in payload["categories"]}

    def test_tree_includes_seeded_categories(self):
        cats = self._cats()
        self.assertIn(self.cat_screws.id, cats)
        self.assertIn(self.cat_conf.id, cats)

    def test_parent_link_is_reported(self):
        cats = self._cats()
        self.assertEqual(cats[self.cat_conf.id]["parent_id"], self.cat_screws.id)

    def test_has_children_flag(self):
        cats = self._cats()
        self.assertTrue(cats[self.cat_screws.id]["has_children"])
        self.assertFalse(cats[self.cat_conf.id]["has_children"])

    def test_count_rolls_up_to_ancestors(self):
        cats = self._cats()
        self.assertGreaterEqual(cats[self.cat_conf.id]["count"], 1)
        self.assertGreaterEqual(
            cats[self.cat_screws.id]["count"], cats[self.cat_conf.id]["count"])
