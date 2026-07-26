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
        # A bad category_id is a bad SELECTION, not a broken category tree —
        # the rail itself is still perfectly computable and must not be
        # wiped out alongside the failed selection.
        self.assertTrue(payload["categories"])

    def test_malformed_facets_degrades_not_raises(self):
        """Every other "degrades not raises" test hits an explicit
        `_degrade` branch (unknown scope, category_id=-1) — none supplies
        input that actually raises inside the try block. A
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

    def test_failed_call_does_not_poison_the_transaction_for_the_next_call(self):
        """A Postgres-level error (negative offset -> "OFFSET must not be
        negative") must not leave the cursor aborted for whatever call comes
        next on the same transaction. Before the fix, get_catalog's `except
        Exception` degraded honestly but never undid the failed SQL, so
        every later ORM call on that cursor — even a completely unrelated,
        perfectly valid one — failed with "current transaction is aborted".
        Only an explicit rollback recovered. Prove the fix by making a
        failing call, then a valid one, on the SAME cursor.
        """
        cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        self.env["product.template"].create({
            "name": "TEST Savepoint-recovery screw",
            "x_southbrook_tool_category_id": cat.id,
        })
        failed = self.Provider.get_catalog(
            scope="tools", category_id=cat.id, offset=-1, limit=3)
        self.assertFalse(failed["ok"])
        recovered = self.Provider.get_catalog(
            scope="tools", category_id=cat.id, offset=0, limit=3)
        self.assertTrue(recovered["ok"])
        self.assertTrue(recovered["rows"])

    def test_malformed_selection_degrades_in_place_but_keeps_the_rail(self):
        """A bad facet selection is scoped to what the user was choosing,
        not to the category tree itself — the rail must survive so the
        failure "degrades in place" instead of looking like a total outage.
        """
        cat = self.env.ref("southbrook_mrp_kitchen_tools.cat_screws")
        payload = self.Provider.get_catalog(
            scope="tools", category_id=cat.id,
            facets={"x_southbrook_thread_type": "not_a_list"})
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["categories"])
        self.assertIn(cat.id, {c["id"] for c in payload["categories"]})

    def test_no_category_does_not_fan_out_across_every_product(self):
        """An unscoped call (category_id=None, matching the OWL component's
        initial `categoryId: null` load) must not search every product on
        the instance. `_columns`/`_facets` already degrade to
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
