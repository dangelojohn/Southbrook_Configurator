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
        """
        rows = {r["name"]: r for r in self._payload()["rows"]}
        self.assertEqual(
            rows["TEST Zero-length spacer"]["x_southbrook_screw_length_mm"],
            0.0)

    def test_null_vs_zero_and_unset_char_via_get_catalog(self):
        """Prove all three absence states in one place, through the real
        get_catalog() path (not private helpers):

        - an explicit 0 on a Float spec (self.c) renders as 0, not a dash
        - the SAME Float spec left unset (self.b) renders as None, not 0
        - a Char spec left unset (self.b) still renders as None

        Postgres genuinely distinguishes NULL from a stored 0 on a Float
        column even though the ORM's read() collapses both to 0.0 — the
        catalog now determines NULL-ness at the SQL layer instead of
        trusting read()'s falsy value.
        """
        rows = {r["name"]: r for r in self._payload()["rows"]}
        self.assertEqual(
            rows["TEST Zero-length spacer"]["x_southbrook_screw_length_mm"],
            0.0)
        self.assertIsNone(
            rows["TEST Pocket screw"]["x_southbrook_screw_length_mm"])
        self.assertIsNone(
            rows["TEST Pocket screw"]["x_southbrook_material_grade"])

    def test_search_matches_name_and_reference(self):
        self.assertIn("TEST Confirmat 7x50",
                      {r["name"] for r in self._payload(search="confirmat")["rows"]})
        self.assertIn("TEST Pocket screw",
                      {r["name"] for r in self._payload(search="SB-PKT")["rows"]})

    def test_search_underscore_is_a_literal_not_a_wildcard(self):
        """`_` is a legitimate character in a part number and must not be
        treated as "match any single character" — a search for a literal
        underscore must match the row that has one and NOT a row that
        merely has some other character in the same position.
        """
        Tmpl = self.env["product.template"]
        Tmpl.create({
            "name": "TEST Underscore Part",
            "default_code": "SBK-TOOL-C_B",
            "x_southbrook_tool_category_id": self.cat.id,
        })
        Tmpl.create({
            "name": "TEST NonUnderscore Part",
            "default_code": "SBK-TOOL-CXB",
            "x_southbrook_tool_category_id": self.cat.id,
        })
        names = {r["name"] for r in self._payload(search="C_B")["rows"]}
        self.assertIn("TEST Underscore Part", names)
        self.assertNotIn("TEST NonUnderscore Part", names)

    def test_search_percent_is_a_literal_not_a_wildcard(self):
        """A bare `%` (or a term containing one) must not turn into
        "match anything" — only a row that genuinely contains that literal
        substring should match.
        """
        Tmpl = self.env["product.template"]
        Tmpl.create({
            "name": "TEST Percent Part",
            "default_code": "SB-50%-TRIM",
            "x_southbrook_tool_category_id": self.cat.id,
        })
        Tmpl.create({
            "name": "TEST NonPercent Part",
            "default_code": "SB-50X-TRIM",
            "x_southbrook_tool_category_id": self.cat.id,
        })
        names = {r["name"] for r in self._payload(search="50%")["rows"]}
        self.assertIn("TEST Percent Part", names)
        self.assertNotIn("TEST NonPercent Part", names)

    def test_search_term_is_trimmed_of_leading_and_trailing_whitespace(self):
        Tmpl = self.env["product.template"]
        Tmpl.create({
            "name": "TEST Padded Panel Match",
            "x_southbrook_tool_category_id": self.cat.id,
        })
        names = {r["name"] for r in self._payload(search="  Panel  ")["rows"]}
        self.assertIn("TEST Padded Panel Match", names)

    def test_limit_zero_follows_odoo_search_semantics_and_returns_everything(self):
        """`limit=0` is documented (get_catalog's docstring) to keep plain
        Odoo search() semantics — "no limit" — rather than being
        special-cased to mean "zero rows". Pin that choice with a test so a
        future change is a deliberate decision, not an accident.
        """
        payload = self._payload(limit=0)
        self.assertEqual(len(payload["rows"]), payload["total"])
        self.assertEqual(payload["total"], 3)

    def test_total_is_count_before_pagination(self):
        payload = self._payload(limit=1)
        self.assertEqual(len(payload["rows"]), 1)
        # Fixture pins this exactly (self.a, self.b, self.c) — a fixed
        # count deserves an exact assertion, not a lower bound.
        self.assertEqual(payload["total"], 3)

    def test_offset_pagination_returns_a_different_correctly_ordered_row(self):
        """offset=1 must return the next row in `default_code, name` order,
        not repeat offset=0's row or silently return nothing.
        """
        first_page = self._payload(limit=1, offset=0)["rows"]
        second_page = self._payload(limit=1, offset=1)["rows"]
        self.assertEqual(len(first_page), 1)
        self.assertEqual(len(second_page), 1)
        self.assertNotEqual(first_page[0]["product_id"], second_page[0]["product_id"])
        # Fixture's default_codes sort as SB-CONF-750, SB-PKT-125, SB-ZERO-000.
        self.assertEqual(first_page[0]["name"], "TEST Confirmat 7x50")
        self.assertEqual(second_page[0]["name"], "TEST Pocket screw")

    def test_many2one_column_renders_display_name_not_tuple_or_id(self):
        """_rows() must route relation values through the same normalizer
        _build_detail() uses, so a declared many2one column never renders
        Odoo's raw (id, display_name) read()-tuple or a bare id.
        """
        vendor = self.env["res.partner"].create({"name": "TEST Vendor Co"})
        self.env["materials.catalog.column"].create({
            "name": "Preferred vendor", "category_id": self.cat.id,
            "field_name": "x_southbrook_preferred_vendor_id", "align": "left",
        })
        self.a.write({"x_southbrook_preferred_vendor_id": vendor.id})
        rows = {r["name"]: r for r in self._payload()["rows"]}
        value = rows["TEST Confirmat 7x50"]["x_southbrook_preferred_vendor_id"]
        self.assertEqual(value, vendor.display_name)
        self.assertNotIsInstance(value, tuple)
        self.assertNotIsInstance(value, int)
