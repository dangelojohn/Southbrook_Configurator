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
