# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestDetail(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_adhesives")
        self.env["materials.catalog.column"].create({
            "name": "Open time (min)", "category_id": self.cat.id,
            "field_name": "x_southbrook_open_time_min", "align": "right",
        })
        self.vendor = self.env["res.partner"].create({
            "name": "TEST Adhesive Supply Co",
        })
        self.uom = self.env.ref("uom.product_uom_unit")
        self.tmpl = self.env["product.template"].create({
            "name": "TEST PVA Type II",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_open_time_min": 8.0,
            "x_southbrook_hazardous": True,
            "x_southbrook_min_stock_qty": 4.0,
            "x_southbrook_preferred_vendor_id": self.vendor.id,
            "x_southbrook_issue_uom_id": self.uom.id,
        })
        self.product = self.tmpl.product_variant_ids[0]

    def test_detail_has_title_and_specs(self):
        detail = self.Provider.get_detail(self.product.id)
        self.assertTrue(detail["ok"])
        self.assertIn("TEST PVA Type II", detail["title"])
        labels = {s["label"]: s["value"] for s in detail["specs"]}
        self.assertEqual(labels["Open time (min)"], 8.0)

    def test_hazard_badge_present(self):
        detail = self.Provider.get_detail(self.product.id)
        self.assertIn("Hazardous", detail["badges"])

    def test_engineering_rail_includes_min_stock(self):
        detail = self.Provider.get_detail(self.product.id)
        labels = {e["label"]: e["value"] for e in detail["engineering"]}
        self.assertEqual(labels["Min stock"], 4.0)

    def test_unknown_product_degrades(self):
        detail = self.Provider.get_detail(-1)
        self.assertFalse(detail["ok"])

    def test_engineering_relation_fields_show_display_name(self):
        """A many2one engineering field (vendor, issue UoM) must render its
        display name string in the payload — never a raw id, and never the
        (id, display_name) tuple Odoo's read() returns internally.
        """
        detail = self.Provider.get_detail(self.product.id)
        labels = {e["label"]: e["value"] for e in detail["engineering"]}
        self.assertEqual(labels["Preferred vendor"], self.vendor.display_name)
        self.assertEqual(labels["Issue UoM"], self.uom.display_name)
        self.assertNotIsInstance(labels["Preferred vendor"], tuple)
        self.assertNotIsInstance(labels["Preferred vendor"], int)
