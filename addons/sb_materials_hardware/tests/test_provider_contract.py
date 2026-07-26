# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged

REQUIRED_KEYS = {"ok", "reason", "scope", "categories", "facets", "columns",
                 "rows", "detail", "total", "provenance"}


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestProviderContract(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Provider = self.env["materials.catalog.provider"]

    def test_payload_has_every_required_key(self):
        payload = self.Provider.get_catalog(scope="tools")
        self.assertTrue(payload["ok"])
        self.assertTrue(REQUIRED_KEYS.issubset(set(payload)))

    def test_unknown_scope_degrades(self):
        payload = self.Provider.get_catalog(scope="does_not_exist")
        self.assertFalse(payload["ok"])
        self.assertIn("reason", payload)

    def test_bad_category_degrades_not_raises(self):
        payload = self.Provider.get_catalog(scope="tools", category_id=-1)
        self.assertFalse(payload["ok"])
        self.assertIn("reason", payload)

    def test_malformed_facets_degrades_not_raises(self):
        """Every other "degrades not raises" test hits an explicit
        `_degrade` branch (unknown scope, category_id=-1) — none supplies
        input that actually raises inside the try block (finding F8). A
        non-dict `facets` reaches `_facet_domain`'s `(facets or {}).items()`
        and must be caught by get_catalog's try/except, not propagate.
        """
        cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        payload = self.Provider.get_catalog(
            scope="tools", category_id=cat.id, facets="not_a_dict")
        self.assertFalse(payload["ok"])
        self.assertIn("reason", payload)
        self.assertTrue(payload["reason"])

    def test_provenance_is_a_string(self):
        payload = self.Provider.get_catalog(scope="tools")
        self.assertIsInstance(payload["provenance"], str)
        self.assertTrue(payload["provenance"])

    def test_no_category_does_not_fan_out_across_every_product(self):
        """An unscoped call (category_id=None, matching the OWL component's
        initial `categoryId: null` load) must not search every product on
        the instance (finding F6). `_columns`/`_facets` already degrade to
        empty for a falsy category; `_rows` must match rather than being
        the one place that still fans out.
        """
        cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.env["product.template"].create({
            "name": "TEST Unscoped-call Screw",
            "x_southbrook_tool_category_id": cat.id,
        })
        payload = self.Provider.get_catalog(scope="tools", category_id=None)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["rows"], [])
        self.assertEqual(payload["total"], 0)
