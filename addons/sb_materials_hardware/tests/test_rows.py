# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestRows(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        # Reuse seeded col_screws_length rather than creating a duplicate
        # (category, field_name) pair which would violate the uniqueness constraint.
        self.env["materials.catalog.column"].search([
            ("category_id", "=", self.cat.id),
            ("field_name", "=", "x_southbrook_screw_length_mm")
        ]) or self.env["materials.catalog.column"].create({
            "name": "Length (mm)", "category_id": self.cat.id,
            "field_name": "x_southbrook_screw_length_mm", "align": "right",
        })
        # Use a field not in the seeded declarations to avoid conflict
        self.env["materials.catalog.column"].create({
            "name": "Material Grade", "category_id": self.cat.id,
            "field_name": "x_southbrook_material_grade", "align": "left",
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
        # Explicit zero — must be reported as 0.0, never folded into None
        # alongside "never entered". See test_explicit_numeric_zero_is_kept.
        self.c = Tmpl.create({
            "name": "TEST Zero-length spacer", "default_code": "SB-ZERO-000",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_screw_length_mm": 0.0,
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

    def test_unset_char_spec_is_none_not_false(self):
        """A never-filled-in Char spec (material grade) reads back as
        None, not the raw False Odoo returns for an unset Char.
        """
        rows = {r["name"]: r for r in self._payload()["rows"]}
        self.assertIsNone(
            rows["TEST Pocket screw"]["x_southbrook_material_grade"])

    def test_explicit_numeric_zero_is_kept_not_folded_to_none(self):
        """An explicitly-entered 0 on a Float spec must render as 0.0, not
        a dash — the catalog must not lie about data that exists.

        Note: a Float spec that was NEVER set also reads back as 0.0 at the
        ORM level (Odoo has no NULL for an unset Float/Integer/Monetary) —
        "never entered" and "entered as zero" are genuinely indistinguishable
        there. This test intentionally does not assert anything about
        self.b's (never-set) x_southbrook_screw_length_mm for that reason;
        it only asserts the case that IS distinguishable: an explicit zero
        must survive as zero.
        """
        rows = {r["name"]: r for r in self._payload()["rows"]}
        self.assertEqual(
            rows["TEST Zero-length spacer"]["x_southbrook_screw_length_mm"],
            0.0)

    def test_search_matches_name_and_reference(self):
        self.assertIn("TEST Confirmat 7x50",
                      {r["name"] for r in self._payload(search="confirmat")["rows"]})
        self.assertIn("TEST Pocket screw",
                      {r["name"] for r in self._payload(search="SB-PKT")["rows"]})

    def test_total_is_count_before_pagination(self):
        payload = self._payload(limit=1)
        self.assertEqual(len(payload["rows"]), 1)
        self.assertGreaterEqual(payload["total"], 3)
