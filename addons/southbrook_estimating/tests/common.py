# SPDX-License-Identifier: LGPL-3.0-only
"""Shared test base class for southbrook_estimating.

Consolidates patterns that previously repeated across 4+ test files:
  - `_ref()` helper for env.ref of southbrook xml_ids
  - Standard model attributes (Partner, Order, Product, Analytics)
  - `_demo_loaded()` guard (replaces duplicate in smoke + demo_data tests)
  - Partner factory helpers for dealer / tradesperson / retail shapes

Use as the base class for any southbrook test that interacts with these
patterns. Tests that need different setup keep using TransactionCase
directly.
"""
from odoo.tests.common import TransactionCase


class SouthbrookTestCase(TransactionCase):
    """Base class for southbrook_estimating tests.

    Subclasses should call super().setUpClass() if they override.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Order = cls.env["sale.order"]
        cls.Product = cls.env["product.product"]
        cls.Analytics = cls.env["southbrook.order.analytics"]

    # ------------------------------------------------------------------
    # xml_id helper
    # ------------------------------------------------------------------
    def _ref(self, xml_id):
        """Resolve a southbrook_estimating xml_id to its record."""
        return self.env.ref(f"southbrook_estimating.{xml_id}")

    # ------------------------------------------------------------------
    # Demo-data guards
    #
    # NF22 (2026-05-30): demo/southbrook_demo_orders.xml was removed
    # from the manifest demo list (it referenced Odoo core demo product
    # `product_product_4` which doesn't exist on a --without-demo DB,
    # AND southbrook templates use dynamic variants so cabinet
    # product.product records don't have xml_ids at install time).
    # Demo PARTNERS still load; demo ORDERS now require a Phase-2
    # Python helper that exercises product.config.session.
    # Two guards now needed:
    #   _demo_loaded()         — demo partners present
    #   _demo_orders_loaded()  — demo orders present (Phase-2 capable)
    # Order-dependent tests must use the second guard.
    # ------------------------------------------------------------------
    def _demo_loaded(self):
        """True when the demo flag loaded the demo partners file."""
        return bool(
            self.env.ref(
                "southbrook_estimating.demo_partner_image_floor",
                raise_if_not_found=False,
            )
        )

    def _demo_orders_loaded(self):
        """True when demo ORDERS are present (Phase-2 helper run)."""
        return bool(
            self.env.ref(
                "southbrook_estimating.demo_order_image_floor_confirmed",
                raise_if_not_found=False,
            )
        )

    # ------------------------------------------------------------------
    # Partner factories — reduce setUpClass boilerplate
    # ------------------------------------------------------------------
    def _make_dealer(self, name="Test Dealer"):
        return self.Partner.create({"name": name, "channel": "dealer"})

    def _make_tradesperson(self, name="Test Tradesperson", tier="3"):
        return self.Partner.create({
            "name": name,
            "channel": "tradesperson",
            "tradesperson_tier": tier,
        })

    def _make_retail(self, name="Test Walk-in"):
        return self.Partner.create({"name": name, "channel": "retail"})
