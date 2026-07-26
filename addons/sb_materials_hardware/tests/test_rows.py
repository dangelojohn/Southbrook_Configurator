# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestRows(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.env["materials.catalog.column"].create({
            "name": "Length (mm)", "category_id": self.cat.id,
            "field_name": "x_southbrook_screw_length_mm", "align": "right",
        })
        Tmpl = self.env["product.template"]
        self.a = Tmpl.create({
            "name": "TEST Confirmat 7x50", "default_code": "SB-CONF-750",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_screw_length_mm": 50.0,
        })
        self.b = Tmpl.create({
            "name": "TEST Pocket screw", "default_code": "SB-PKT-125",
            "x_southbrook_tool_category_id": self.cat.id,
        })

    def _payload(self, **kw):
        return self.Provider.get_catalog(
            scope="tools", category_id=self.cat.id, **kw)

    def test_rows_are_keyed_on_product_id(self):
        rows = self._payload()["rows"]
        self.assertTrue(rows)
        self.assertIn("product_id", rows[0])

    def test_row_carries_declared_column_value(self):
        rows = {r["name"]: r for r in self._payload()["rows"]}
        self.assertEqual(
            rows["TEST Confirmat 7x50"]["x_southbrook_screw_length_mm"], 50.0)

    def test_absent_spec_is_none_not_zero(self):
        rows = {r["name"]: r for r in self._payload()["rows"]}
        self.assertIsNone(rows["TEST Pocket screw"]["x_southbrook_screw_length_mm"])

    def test_search_matches_name_and_reference(self):
        self.assertIn("TEST Confirmat 7x50",
                      {r["name"] for r in self._payload(search="confirmat")["rows"]})
        self.assertIn("TEST Pocket screw",
                      {r["name"] for r in self._payload(search="SB-PKT")["rows"]})

    def test_total_is_count_before_pagination(self):
        payload = self._payload(limit=1)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertGreaterEqual(payload["total"], 2)
