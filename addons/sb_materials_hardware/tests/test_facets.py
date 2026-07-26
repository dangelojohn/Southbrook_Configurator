# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestFacets(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]
        self.Facet = self.env["materials.catalog.facet"]
        self.cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_abr_disc")
        Tmpl = self.env["product.template"]
        for grit in ["80", "120", "220", "100"]:
            Tmpl.create({
                "name": "TEST Disc %s" % grit,
                "x_southbrook_tool_category_id": self.cat.id,
                "x_southbrook_grit": grit,
            })
        Tmpl.create({
            "name": "TEST Disc assorted",
            "x_southbrook_tool_category_id": self.cat.id,
            "x_southbrook_grit": "assorted",
        })

    def test_numeric_prefix_helper(self):
        f = self.Provider._numeric_prefix
        self.assertEqual(f("120"), 120.0)
        self.assertEqual(f("120 grit"), 120.0)
        self.assertIsNone(f("assorted"))
        self.assertIsNone(f(False))

    def _facet(self, key):
        payload = self.Provider.get_catalog(scope="tools", category_id=self.cat.id)
        return {f["key"]: f for f in payload["facets"]}[key]

    def test_enum_distinct_values_are_numerically_ordered(self):
        self.Facet.create({
            "name": "Grit", "category_id": self.cat.id,
            "field_name": "x_southbrook_grit", "facet_type": "enum_distinct",
        })
        values = [v["value"] for v in self._facet("x_southbrook_grit")["values"]]
        numeric = [v for v in values if v != "assorted"]
        self.assertEqual(numeric, ["80", "100", "120", "220"])

    def test_unparseable_value_sorts_last_and_is_kept(self):
        self.Facet.create({
            "name": "Grit", "category_id": self.cat.id,
            "field_name": "x_southbrook_grit", "facet_type": "enum_distinct",
        })
        values = [v["value"] for v in self._facet("x_southbrook_grit")["values"]]
        self.assertEqual(values[-1], "assorted")

    def test_enum_facet_uses_selection_labels(self):
        cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.env["product.template"].create({
            "name": "TEST Confirmat", "x_southbrook_tool_category_id": cat.id,
            "x_southbrook_thread_type": "confirmat",
        })
        self.Facet.create({
            "name": "Thread type", "category_id": cat.id,
            "field_name": "x_southbrook_thread_type", "facet_type": "enum",
        })
        payload = self.Provider.get_catalog(scope="tools", category_id=cat.id)
        facet = {f["key"]: f for f in payload["facets"]}["x_southbrook_thread_type"]
        labels = {v["value"]: v["label"] for v in facet["values"]}
        self.assertEqual(labels["confirmat"], "Confirmat")

    def test_range_facet_reports_min_and_max(self):
        cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        Tmpl = self.env["product.template"]
        for length in [30.0, 50.0, 70.0]:
            Tmpl.create({
                "name": "TEST Screw %s" % length,
                "x_southbrook_tool_category_id": cat.id,
                "x_southbrook_screw_length_mm": length,
            })
        self.Facet.create({
            "name": "Length", "category_id": cat.id,
            "field_name": "x_southbrook_screw_length_mm", "facet_type": "range",
        })
        payload = self.Provider.get_catalog(scope="tools", category_id=cat.id)
        facet = {f["key"]: f for f in payload["facets"]}[
            "x_southbrook_screw_length_mm"]
        self.assertEqual(facet["min"], 30.0)
        self.assertEqual(facet["max"], 70.0)
