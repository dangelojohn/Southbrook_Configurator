# SPDX-License-Identifier: LGPL-3.0-only
"""P2 — Brand-aware Drawer Slide seed + derivation.

The seed function creates the "Drawer Slide" product.attribute + 5 values
and wires the attribute to every template that already exposes a
"Drawer Construction" attribute. is_soft_close_slide_picked() is the
backbone for the derived badge the audit asked for.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.southbrook_configurator_ux.models.drawer_slide_p2 import (
    DRAWER_SLIDE_ATTR_NAME,
    DRAWER_SLIDE_OPTIONS,
    is_soft_close_slide,
    slide_sku_for_value_name,
)


@tagged("post_install", "-at_install", "southbrook", "configurator_ux", "p2",
        "drawer_slide_seed")
class TestP2DrawerSlideSeed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Seed = cls.env["southbrook.configurator_ux.drawer_slide_seed"]
        cls.Attribute = cls.env["product.attribute"]
        cls.AttributeValue = cls.env["product.attribute.value"]

    # ------------------------------------------------------------------
    # Seed idempotency
    # ------------------------------------------------------------------
    def test_seed_creates_attribute_with_five_values(self):
        # The data file fires the seed at install/-u; re-running here
        # should be a no-op.
        attribute = self.Seed.seed_drawer_slide_attribute()
        self.assertEqual(attribute.name, DRAWER_SLIDE_ATTR_NAME)
        self.assertEqual(
            self.AttributeValue.search_count(
                [("attribute_id", "=", attribute.id)]),
            len(DRAWER_SLIDE_OPTIONS),
            "exactly the 5 audit-named slide options must be seeded")

    def test_seed_is_idempotent(self):
        attribute = self.Seed.seed_drawer_slide_attribute()
        before = self.AttributeValue.search_count(
            [("attribute_id", "=", attribute.id)])
        # Re-run.
        self.Seed.seed_drawer_slide_attribute()
        after = self.AttributeValue.search_count(
            [("attribute_id", "=", attribute.id)])
        self.assertEqual(before, after, "re-seeding must not duplicate values")

    # ------------------------------------------------------------------
    # Pure-Python helpers (drive the UI badge derivation)
    # ------------------------------------------------------------------
    def test_is_soft_close_slide_table_consistency(self):
        # The K2832 is a soft-close model; the 3032 ball-bearing isn't.
        # These two rows are the audit's primary acceptance examples.
        self.assertTrue(
            is_soft_close_slide("King Slide K2832 21\" Soft-Close"))
        self.assertFalse(
            is_soft_close_slide("King Slide 3032 18\" Ball-Bearing"))
        # Unknown / None safe.
        self.assertFalse(is_soft_close_slide(None))
        self.assertFalse(is_soft_close_slide(""))
        self.assertFalse(is_soft_close_slide("Unknown Brand"))

    def test_slide_sku_for_value_name(self):
        self.assertEqual(
            slide_sku_for_value_name("King Slide K2832 21\" Soft-Close"),
            "KS-K2832-21",
            "value name -> Marathon SKU mapping must hit the actual catalog")
        self.assertEqual(
            slide_sku_for_value_name("Blum MOVENTO 450"), "BLM-MOV-450")
        self.assertIsNone(slide_sku_for_value_name("not a slide"))

    # ------------------------------------------------------------------
    # Session-based helpers — derived badge + SKU resolution
    # ------------------------------------------------------------------
    def test_session_helpers_return_none_when_no_session(self):
        self.assertIsNone(self.Seed.slide_sku_from_session(None))
        # Empty value_ids recordset.
        empty = self.AttributeValue.browse([])
        self.assertFalse(self.Seed.is_soft_close_slide_picked(empty))
