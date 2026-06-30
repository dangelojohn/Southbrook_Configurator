# SPDX-License-Identifier: LGPL-3.0-only
"""W008 — ProductGraph back-references on southbrook.asbuilt.

Verifies the stored-related field wire-up that closes the warranty
trace loop (cabinet serial -> MO -> engineering revision in 1 hop).
See MFG-REVIEW-R4 W4 + MFG-REVIEW-R9 master roadmap W008.

The fields:
  - pg_release_id     -> related production_id.pg_release_id, stored
  - pg_revision_code  -> related production_id.pg_revision_code, stored
  - pg_ebom_id        -> related production_id.pg_ebom_id, stored
  - pg_root_item_id   -> related production_id.pg_root_item_id, stored

We don't fabricate a full pg.release fixture here (heavy + crosses the
governance boundary R1). Instead we assert:
  1. The fields exist on the model with the expected comodels.
  2. They are stored + readonly + indexed (so warranty queries are fast).
  3. They are `related` walks of production_id.pg_*.
  4. A fresh asbuilt on an MO with no pg.release has all four fields
     unset (no crash, no spurious values).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "w008")
class TestAsbuiltPgBackrefs(TransactionCase):

    def test_fields_exist_on_asbuilt(self):
        Asbuilt = self.env["southbrook.asbuilt"]
        for fname in (
            "pg_release_id",
            "pg_revision_code",
            "pg_ebom_id",
            "pg_root_item_id",
        ):
            self.assertIn(
                fname, Asbuilt._fields,
                f"southbrook.asbuilt missing W008 field {fname!r}",
            )

    def test_pg_release_id_is_stored_related_to_mo(self):
        f = self.env["southbrook.asbuilt"]._fields["pg_release_id"]
        self.assertEqual(f.comodel_name, "pg.release")
        self.assertTrue(f.store, "pg_release_id must be stored for "
                                  "warranty-trace queries to be fast")
        self.assertTrue(f.readonly, "pg_release_id is a snapshot — readonly")
        self.assertTrue(f.index, "pg_release_id must be indexed")
        self.assertEqual(
            f.related, ("production_id", "pg_release_id"),
            "pg_release_id must walk production_id.pg_release_id",
        )

    def test_pg_revision_code_is_stored_related_to_mo(self):
        f = self.env["southbrook.asbuilt"]._fields["pg_revision_code"]
        self.assertEqual(f.type, "char")
        self.assertTrue(f.store)
        self.assertTrue(f.readonly)
        self.assertTrue(f.index)
        self.assertEqual(
            f.related, ("production_id", "pg_revision_code"),
        )

    def test_pg_ebom_id_is_stored_related_to_mo(self):
        f = self.env["southbrook.asbuilt"]._fields["pg_ebom_id"]
        self.assertEqual(f.comodel_name, "pg.ebom")
        self.assertTrue(f.store)
        self.assertTrue(f.readonly)
        self.assertTrue(f.index)
        self.assertEqual(
            f.related, ("production_id", "pg_ebom_id"),
        )

    def test_pg_root_item_id_is_stored_related_to_mo(self):
        f = self.env["southbrook.asbuilt"]._fields["pg_root_item_id"]
        self.assertEqual(f.comodel_name, "pg.item")
        self.assertTrue(f.store)
        self.assertTrue(f.readonly)
        self.assertTrue(f.index)
        self.assertEqual(
            f.related, ("production_id", "pg_root_item_id"),
        )

    def test_mo_supplies_the_pg_fields(self):
        """Sanity: the related-walk source actually exists on
        mrp.production (added by product_graph_release via PG-112).
        Without these the related walk would fail at registry build."""
        Production = self.env["mrp.production"]
        for fname in (
            "pg_release_id",
            "pg_revision_code",
            "pg_ebom_id",
            "pg_root_item_id",
        ):
            self.assertIn(
                fname, Production._fields,
                f"mrp.production missing {fname!r} — product_graph_release "
                f"depends should pull this in via the manifest",
            )

    def test_unset_when_mo_has_no_release(self):
        """An asbuilt whose MO never went through a pg.release should
        have all four fields empty — no fabricated values, no crash."""
        Asbuilt = self.env["southbrook.asbuilt"]
        Production = self.env["mrp.production"]
        # Find any MO without a pg_release_id. There are plenty in
        # a fresh install; skip the test if somehow not.
        mo = Production.search(
            [("pg_release_id", "=", False)], limit=1,
        )
        if not mo:
            self.skipTest("no MO without pg_release_id available")
        ab = Asbuilt.create({
            "production_id": mo.id,
            "serial_number": "W008-TEST",
        })
        try:
            # All four back-refs follow the empty source -> empty.
            self.assertFalse(ab.pg_release_id)
            self.assertFalse(ab.pg_revision_code)
            self.assertFalse(ab.pg_ebom_id)
            self.assertFalse(ab.pg_root_item_id)
        finally:
            # Clean up — asbuilts don't auto-delete with the MO in
            # this synthesized path (we picked an existing MO).
            ab.unlink()
