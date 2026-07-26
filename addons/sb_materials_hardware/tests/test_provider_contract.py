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

    def test_provenance_is_a_string(self):
        payload = self.Provider.get_catalog(scope="tools")
        self.assertIsInstance(payload["provenance"], str)
        self.assertTrue(payload["provenance"])
