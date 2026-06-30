# SPDX-License-Identifier: LGPL-3.0-only
"""A1 — Prodboard cabinet-archetype taxonomy seed.

Asserts the seed produces 223 archetypes (160 Classic + 63 Handleless),
classifies each into the correct body_class, parses image URLs into
UUID + filename, and is idempotent on re-run.
"""
import json

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "estimating", "a1",
        "prodboard_taxonomy")
class TestA1ProdboardTaxonomy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Taxonomy = cls.env["southbrook.estimating.prodboard_taxonomy"]
        cls.Archetype = cls.env["southbrook.cabinet.archetype"]

    # ------------------------------------------------------------------
    # Acceptance — seed creates the expected archetype counts
    # ------------------------------------------------------------------
    def test_seed_produces_223_archetypes(self):
        # Seed already ran via the XML data file on -i/-u; re-running
        # is the idempotent assertion below. Here we just count the
        # outcome.
        all_count = self.Archetype.search_count([])
        self.assertGreaterEqual(
            all_count, 223,
            "expected at least 223 archetypes seeded from the JSON "
            "source (160 Classic + 63 Handleless)")
        classic = self.Archetype.search_count(
            [("collection", "=", "classic")])
        handleless = self.Archetype.search_count(
            [("collection", "=", "handleless")])
        self.assertEqual(classic, 160, "expected 160 Classic Collection")
        self.assertEqual(handleless, 63, "expected 63 True Handleless")

    # ------------------------------------------------------------------
    # Acceptance — body_class classification
    # ------------------------------------------------------------------
    def test_body_classification_known_examples(self):
        # CC-BHL1DR is a base archetype, type HL.
        a = self.Archetype.search([("code", "=", "CC-BHL1DR")], limit=1)
        self.assertTrue(a)
        self.assertEqual(a.body_class, "base")
        self.assertEqual(a.cabinet_type, "HL")
        self.assertEqual(a.cabinet_type_label, "Highline")
        # CC-CHL{S}MC is a corner archetype with Magic Corner suffix.
        a = self.Archetype.search([("code", "=", "CC-CHL{S}MC")], limit=1)
        self.assertTrue(a)
        self.assertEqual(a.body_class, "corner")
        # CC-WD{H}1DR is a wall archetype with door 1DR.
        a = self.Archetype.search([("code", "=", "CC-WD{H}1DR")], limit=1)
        self.assertTrue(a)
        self.assertEqual(a.body_class, "wall")
        # CC-TA{H}DO2DR is a tall archetype.
        a = self.Archetype.search([("code", "=", "CC-TA{H}DO2DR")], limit=1)
        self.assertTrue(a)
        self.assertEqual(a.body_class, "tall")

    # ------------------------------------------------------------------
    # Acceptance — width_available is preserved as a JSON list
    # ------------------------------------------------------------------
    def test_width_array_preserved(self):
        a = self.Archetype.search([("code", "=", "CC-BHL1DR")], limit=1)
        widths = json.loads(a.width_available_json or "[]")
        self.assertEqual(
            widths,
            [150, 200, 250, 260, 300, 350, 400, 450, 500, 550, 600],
            "CC-BHL1DR's width grid must match the JSON source")
        self.assertEqual(a.width_default_mm, 400)

    # ------------------------------------------------------------------
    # Acceptance — image URLs are decomposed into uuid + filename
    # ------------------------------------------------------------------
    def test_image_uuid_extracted(self):
        a = self.Archetype.search([("code", "=", "CC-BHL1DR")], limit=1)
        self.assertEqual(a.image_uuid,
                         "c3d44b09-2933-46d2-9f1e-4a6c8b8b838d")
        self.assertIn("Highline Base Unit.png", a.image_filename or "")

    # ------------------------------------------------------------------
    # Acceptance — seed is idempotent
    # ------------------------------------------------------------------
    def test_seed_is_idempotent(self):
        before = self.Archetype.search_count([])
        created, updated, _ = self.Taxonomy.seed_from_json()
        after = self.Archetype.search_count([])
        self.assertEqual(
            before, after,
            "re-running the seed must not create duplicates")
        self.assertEqual(
            created, 0,
            "all rows should be UPDATEs, not creates, on re-run")
        self.assertGreater(updated, 0,
                           "the seed must have visited some rows")
