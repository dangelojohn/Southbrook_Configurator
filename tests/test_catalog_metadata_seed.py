# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the 2026-06-02 catalog-picker metadata fields.

Asserts the four new product.template fields
(southbrook_category / southbrook_description / southbrook_dimensions /
southbrook_icon_key) are populated by data/cabinet_catalog_metadata.xml
on every Q8 cabinet template, and that category values are inside the
allowed Selection set.

Why this test exists:

  - cabinet_catalog_metadata.xml is hand-curated and grew alongside
    the redesign. A future contributor who renames an xml_id, drops
    a record while testing locally, or mis-spells a category enum
    would silently break the customer Order Builder's catalog grid
    (empty descriptions, missing icons, dropped category pills).
    This is the gate that catches it before deploy.

  - The migration backfill at migrations/19.0.1.1.0/post-migrate.py
    only runs on upgrade (when `version` is truthy). Fresh-install
    DBs depend solely on the data file. This test covers the
    fresh-install path; the migration is integration-tested by the
    fact that the live QNAP stack already on 19.0.1.0.0 upgrades
    successfully to 19.0.1.1.0.

Access-rights note: the four fields are vanilla Char / Selection on
product.template — they inherit the model-level ir.model.access ACLs
already shipped with product_configurator + Odoo core. No new
ir.model.access.csv rows needed.
"""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


# The 12 Q8 cabinet xml_ids, paired with their expected category +
# icon_key. The full description + dimensions strings are not
# duplicated here — that's what cabinet_catalog_metadata.xml is for —
# but we DO assert they are non-empty (the seed file populated them).
_EXPECTED = [
    ("wall_1dr",     "Wall",   "wall1"),
    ("wall_2dr",     "Wall",   "wall2"),
    ("base_1dr",     "Base",   "base1"),
    ("base_2dr",     "Base",   "base2"),
    ("drawer_bank",  "Drawer", "drawer"),
    ("sink_base",    "Base",   "sink"),
    ("tall_pantry",  "Tall",   "pantry"),
    ("tall_oven",    "Tall",   "oven"),
    ("corner",       "Base",   "corner"),
    ("vanity",       "Vanity", "vanity"),
    ("accessory",    "Extras", "extra"),
    ("worktop",      "Extras", "worktop"),
]

_ALLOWED_CATEGORIES = {
    "Wall", "Base", "Drawer", "Tall", "Vanity", "Extras",
}


@tagged("post_install", "-at_install", "southbrook_catalog_metadata")
class TestCatalogMetadataSeed(SouthbrookTestCase):

    def test_all_twelve_cabinets_have_southbrook_metadata_populated(self):
        """Every Q8 cabinet template carries non-empty values for the
        four southbrook_* metadata fields after install / -u.
        """
        for xml_id, _expected_cat, _expected_icon in _EXPECTED:
            tmpl = self._ref(xml_id)
            self.assertTrue(
                tmpl.southbrook_category,
                f"{xml_id}.southbrook_category is empty — "
                f"data/cabinet_catalog_metadata.xml seed missed this row",
            )
            self.assertTrue(
                tmpl.southbrook_description,
                f"{xml_id}.southbrook_description is empty — catalog "
                f"picker card would render with no description",
            )
            self.assertTrue(
                tmpl.southbrook_dimensions,
                f"{xml_id}.southbrook_dimensions is empty — catalog "
                f"picker card would render with no dimension callout",
            )
            self.assertTrue(
                tmpl.southbrook_icon_key,
                f"{xml_id}.southbrook_icon_key is empty — catalog "
                f"picker would render the 'extra' fallback icon",
            )

    def test_category_values_are_within_allowed_selection(self):
        """Every cabinet's southbrook_category value is one of the six
        valid Selection keys. Catches typos in the seed XML that
        would slip past Odoo's loose Char-vs-Selection-key check
        (Odoo validates Selection on write through the form view but
        an XML <field> can sneak through if the underlying column
        accepts the value).
        """
        for xml_id, _expected_cat, _expected_icon in _EXPECTED:
            tmpl = self._ref(xml_id)
            self.assertIn(
                tmpl.southbrook_category,
                _ALLOWED_CATEGORIES,
                f"{xml_id}.southbrook_category={tmpl.southbrook_category!r} "
                f"is not one of the six allowed values "
                f"{sorted(_ALLOWED_CATEGORIES)}",
            )

    def test_per_cabinet_category_and_icon_match_expected_mapping(self):
        """The category + icon_key mapping exactly matches the
        user's redesign brief mapping (so that, e.g., SB-CORNER
        stays a Base rather than getting reclassified as Extras by a
        well-meaning future edit).
        """
        for xml_id, expected_cat, expected_icon in _EXPECTED:
            tmpl = self._ref(xml_id)
            self.assertEqual(
                tmpl.southbrook_category, expected_cat,
                f"{xml_id} should map to category {expected_cat!r}, "
                f"got {tmpl.southbrook_category!r}",
            )
            self.assertEqual(
                tmpl.southbrook_icon_key, expected_icon,
                f"{xml_id} should map to icon_key {expected_icon!r}, "
                f"got {tmpl.southbrook_icon_key!r}",
            )

    def test_southbrook_description_field_is_translatable(self):
        """The translatable flag on southbrook_description is what the
        kitchen_planner_state controller relies on to render the
        description in the visitor's active language without an
        explicit with_context(lang=...) call. If a future contributor
        drops translate=True, the catalog would silently serve English
        to non-English visitors.
        """
        field = self.env["product.template"]._fields.get(
            "southbrook_description",
        )
        self.assertIsNotNone(
            field, "southbrook_description field missing on product.template",
        )
        self.assertTrue(
            getattr(field, "translate", False),
            "southbrook_description should be translatable so the "
            "catalog picker can localise per visitor language",
        )

    def test_southbrook_description_resolves_in_active_language(self):
        """Writing a translation for southbrook_description and then
        reading the field under a different active language returns
        the translated string. Covers the end-to-end path the
        kitchen_planner_state controller relies on for non-English
        Southbrook deployments.
        """
        # Install a second language we can switch into. Odoo's
        # base lang install path may not be available in every test
        # DB; gracefully skip if so.
        Lang = self.env["res.lang"]
        es = Lang.with_context(active_test=False).search([
            ("code", "=", "es_ES"),
        ], limit=1)
        if not es:
            # Attempt activation; fall back to skip if the language
            # bundle isn't installable in this DB.
            try:
                Lang._activate_lang("es_ES")
                es = Lang.with_context(active_test=False).search([
                    ("code", "=", "es_ES"),
                ], limit=1)
            except Exception:
                self.skipTest("es_ES not activatable in this DB")
            if not es:
                self.skipTest("es_ES not present after activate attempt")

        tmpl = self._ref("base_1dr")
        original = tmpl.southbrook_description

        # Write the Spanish translation.
        tmpl.with_context(lang="es_ES").southbrook_description = (
            "Mueble bajo de una puerta con estante ajustable."
        )

        # Re-read under the active es lang.
        tmpl_es = tmpl.with_context(lang="es_ES")
        self.assertEqual(
            tmpl_es.southbrook_description,
            "Mueble bajo de una puerta con estante ajustable.",
            "Translation should resolve under active es_ES context",
        )
        # And the English original is preserved on the en_US side.
        tmpl_en = tmpl.with_context(lang="en_US")
        self.assertEqual(
            tmpl_en.southbrook_description, original,
            "English original should be preserved (translation must "
            "not overwrite the source-language value)",
        )

    def test_field_acls_inherit_from_product_template(self):
        """Sanity check that the four fields are visible to portal
        users without bespoke ir.model.access rows. The customer
        Order Builder fetches them via the kitchen_planner_state
        endpoint, which uses sudo() on product.template anyway, but
        the fields should also be normally readable so the backend
        form view + non-sudo'd code paths work.
        """
        portal_user = self.env.ref("base.public_user", raise_if_not_found=False)
        if not portal_user:
            # Some test DBs don't ship base.public_user — skip rather
            # than hard-fail (defensive parity with the OCA test style).
            self.skipTest("base.public_user not present in this DB")
        # Reading southbrook_* off a template as the public user
        # should not raise AccessError. product.template is publicly
        # readable for website_sale's /shop catalog, and our four
        # fields are vanilla Char/Selection on the same model.
        tmpl = self._ref("base_1dr").with_user(portal_user)
        # Triggering field read; just touching the attributes is
        # enough to provoke any access-check.
        _ = (
            tmpl.southbrook_category,
            tmpl.southbrook_description,
            tmpl.southbrook_dimensions,
            tmpl.southbrook_icon_key,
        )
