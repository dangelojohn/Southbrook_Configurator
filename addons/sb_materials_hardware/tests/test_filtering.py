# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestFiltering(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        Tmpl = self.env["product.template"]
        self.confirmat = Tmpl.create({
            "name": "TEST Confirmat 7x50", "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": 50.0,
        })
        self.euro = Tmpl.create({
            "name": "TEST Euro 6.3x13", "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "euro",
            "x_southbrook_screw_length_mm": 13.0,
        })
        self.coarse = Tmpl.create({
            "name": "TEST Coarse 4x40", "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "coarse",
            "x_southbrook_screw_length_mm": 40.0,
        })

    def _matching(self, facets):
        """Apply the facet domain directly to product.template.

        This task is tested against the DOMAIN BUILDER, not against rows —
        rows arrive in Task 8. Keeping the test at this level is what makes
        Task 7 independently green.
        """
        domain = self.env["tools.catalog.provider"]._facet_domain(facets)
        base = [("x_southbrook_tool_category_id", "child_of", self.cat.id)]
        return set(self.env["product.template"].search(base + domain).mapped("name"))

    def test_single_value_filters(self):
        names = self._matching({"x_southbrook_thread_type": ["confirmat"]})
        self.assertIn("TEST Confirmat 7x50", names)
        self.assertNotIn("TEST Euro 6.3x13", names)

    def test_multi_select_within_facet_is_or(self):
        names = self._matching({"x_southbrook_thread_type": ["confirmat", "euro"]})
        self.assertIn("TEST Confirmat 7x50", names)
        self.assertIn("TEST Euro 6.3x13", names)
        self.assertNotIn("TEST Coarse 4x40", names)

    def test_across_facets_is_and(self):
        names = self._matching({
            "x_southbrook_thread_type": ["confirmat", "euro"],
            "x_southbrook_screw_length_mm": {"min": 40.0, "max": 60.0},
        })
        self.assertIn("TEST Confirmat 7x50", names)
        self.assertNotIn("TEST Euro 6.3x13", names)

    def test_empty_facets_returns_everything_in_category(self):
        names = self._matching({})
        self.assertTrue({"TEST Confirmat 7x50", "TEST Euro 6.3x13",
                         "TEST Coarse 4x40"}.issubset(names))

    def test_unknown_field_is_ignored_not_crashed(self):
        names = self._matching({"x_southbrook_not_a_field": ["anything"]})
        self.assertIn("TEST Confirmat 7x50", names)


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestFilteringEndToEnd(TransactionCase):
    """_rows() re-wraps every `_facet_domain` leaf as
    `product_tmpl_id.<field>` before applying it to product.product — the
    tests above apply the domain builder's output directly to
    product.template, unprefixed, so that transform was never exercised.
    If it broke, every facet click would silently return
    everything while all the facet/filter tests above stayed green. These
    go through the real entry point, get_catalog(), instead.
    """

    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        Tmpl = self.env["product.template"]
        self.confirmat = Tmpl.create({
            "name": "TEST E2E Confirmat 7x50",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": 50.0,
        })
        self.euro = Tmpl.create({
            "name": "TEST E2E Euro 6.3x13",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "euro",
            "x_southbrook_screw_length_mm": 13.0,
        })
        self.coarse = Tmpl.create({
            "name": "TEST E2E Coarse 4x40",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "coarse",
            "x_southbrook_screw_length_mm": 40.0,
        })

    def _names(self, facets):
        payload = self.Provider.get_catalog(
            scope="tools", category_id=self.cat.id, facets=facets)
        self.assertTrue(payload["ok"])
        return {r["name"] for r in payload["rows"]}, payload["total"]

    def test_enum_facet_narrows_rows_through_get_catalog(self):
        names, total = self._names({"x_southbrook_thread_type": ["confirmat"]})
        self.assertIn("TEST E2E Confirmat 7x50", names)
        self.assertNotIn("TEST E2E Euro 6.3x13", names)
        self.assertNotIn("TEST E2E Coarse 4x40", names)
        self.assertEqual(total, 1)

    def test_range_facet_narrows_rows_through_get_catalog(self):
        names, total = self._names(
            {"x_southbrook_screw_length_mm": {"min": 40.0, "max": 60.0}})
        self.assertIn("TEST E2E Confirmat 7x50", names)
        self.assertIn("TEST E2E Coarse 4x40", names)
        self.assertNotIn("TEST E2E Euro 6.3x13", names)
        self.assertEqual(total, 2)

    def test_combined_enum_and_range_facets_narrow_rows_through_get_catalog(self):
        names, total = self._names({
            "x_southbrook_thread_type": ["confirmat", "coarse"],
            "x_southbrook_screw_length_mm": {"min": 45.0, "max": 60.0},
        })
        self.assertIn("TEST E2E Confirmat 7x50", names)
        self.assertNotIn("TEST E2E Coarse 4x40", names)   # length 40 < 45
        self.assertNotIn("TEST E2E Euro 6.3x13", names)   # wrong thread type
        self.assertEqual(total, 1)

    def test_max_only_range_excludes_unset_but_keeps_genuine_zero(self):
        """A max-only range facet must exclude a row where the field was
        never set, while still returning a row whose value is a genuine
        stored 0. `length <= 50` naively matches unset rows too, because
        Odoo's domain-to-SQL layer ORs in "field IS NULL" whenever the
        field's falsy value (0 for Float/Integer/Monetary) itself satisfies
        the comparison. Go through get_catalog(), the real entry point, not
        `_facet_domain` directly.
        """
        Tmpl = self.env["product.template"]
        Tmpl.create({
            "name": "TEST E2E Zero-length screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": 0.0,
        })
        Tmpl.create({
            "name": "TEST E2E In-range screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": 25.0,
        })
        Tmpl.create({
            "name": "TEST E2E Unset-length screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            # x_southbrook_screw_length_mm intentionally left unset -> NULL
        })
        names, total = self._names(
            {"x_southbrook_screw_length_mm": {"max": 50.0}})
        self.assertIn("TEST E2E Zero-length screw", names)
        self.assertIn("TEST E2E In-range screw", names)
        self.assertNotIn("TEST E2E Unset-length screw", names)
        self.assertEqual(total, len(names))

    def test_min_only_range_with_zero_lower_bound_excludes_unset_but_keeps_zero(self):
        """The same NULL-vs-zero danger zone the code's own comment names
        also applies to a MIN-only range whose bound is exactly 0: `length
        >= 0` is satisfied by NULL's coerced falsy value (0) just as
        `length <= 50` was in the max-only case above, so a min-only leaf
        with `low == 0` must take the same NOT-NULL custom-SQL path.
        """
        Tmpl = self.env["product.template"]
        Tmpl.create({
            "name": "TEST E2E Min-zero screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": 0.0,
        })
        Tmpl.create({
            "name": "TEST E2E Min-positive screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": 25.0,
        })
        Tmpl.create({
            "name": "TEST E2E Min-unset screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            # x_southbrook_screw_length_mm intentionally left unset -> NULL
        })
        names, total = self._names(
            {"x_southbrook_screw_length_mm": {"min": 0.0}})
        self.assertIn("TEST E2E Min-zero screw", names)
        self.assertIn("TEST E2E Min-positive screw", names)
        self.assertNotIn("TEST E2E Min-unset screw", names)
        self.assertEqual(total, len(names))

    def test_both_bounds_straddling_zero_excludes_unset_but_keeps_zero_and_negative(self):
        """A two-sided range whose bounds straddle zero (min < 0 < max) is
        the third danger-zone shape the code's own comment names: NULL's
        coerced falsy value (0) satisfies both `>= low` and `<= high` here
        too, so this must also take the NOT-NULL custom-SQL path — proven
        with a genuinely negative in-range value alongside zero, not just
        zero alone, so a fix that only special-cases 0 would still fail
        this test on the -5 row.
        """
        Tmpl = self.env["product.template"]
        Tmpl.create({
            "name": "TEST E2E Straddle-zero screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": 0.0,
        })
        Tmpl.create({
            "name": "TEST E2E Straddle-negative screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": -5.0,
        })
        Tmpl.create({
            "name": "TEST E2E Straddle-out-of-range screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            "x_southbrook_screw_length_mm": 20.0,
        })
        Tmpl.create({
            "name": "TEST E2E Straddle-unset screw",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_thread_type": "confirmat",
            # x_southbrook_screw_length_mm intentionally left unset -> NULL
        })
        names, total = self._names(
            {"x_southbrook_screw_length_mm": {"min": -10.0, "max": 10.0}})
        self.assertIn("TEST E2E Straddle-zero screw", names)
        self.assertIn("TEST E2E Straddle-negative screw", names)
        self.assertNotIn("TEST E2E Straddle-out-of-range screw", names)
        self.assertNotIn("TEST E2E Straddle-unset screw", names)
        self.assertEqual(total, len(names))
