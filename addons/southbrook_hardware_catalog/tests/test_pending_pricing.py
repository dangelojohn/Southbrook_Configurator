# SPDX-License-Identifier: LGPL-3.0-only
"""Pending-pricing flag — every seed SKU ships with x_pricing_pending=True
because the trade-account workbook isn't on disk yet. Once a real cost
lands, the flag flips. Tests guard both directions of that contract.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "hardware_catalog",
        "pending_pricing")
class TestPendingPricing(TransactionCase):

    def test_every_seed_sku_is_pricing_pending(self):
        """Until the trade-account import lands, every seeded hardware
        SKU must carry x_pricing_pending=True so the BoM consumers know
        the cost is provisional."""
        Product = self.env["product.product"]
        hardware = Product.search([("x_hardware_category", "!=", False)])
        unflagged = hardware.filtered(lambda p: not p.x_pricing_pending)
        self.assertFalse(
            unflagged,
            "These hardware SKUs are missing x_pricing_pending=True: "
            f"{unflagged.mapped('display_name')}",
        )

    def test_flag_is_indexed(self):
        """The flag is queried often (find pending SKUs for the reconciliation
        UI) — must be DB-indexed."""
        field = self.env["product.product"]._fields["x_pricing_pending"]
        self.assertTrue(field.index, "x_pricing_pending must be DB-indexed")

    def test_pending_skus_searchable(self):
        """Search-domain round-trip — pending=True returns only pending SKUs."""
        Product = self.env["product.product"]
        pending = Product.search([("x_pricing_pending", "=", True),
                                  ("x_hardware_category", "!=", False)])
        non_pending = Product.search([("x_pricing_pending", "=", False),
                                      ("x_hardware_category", "!=", False)])
        # No overlap.
        self.assertFalse(pending & non_pending)

    def test_clear_flag_after_cost_lands(self):
        """When a cost actually lands, clearing the flag is the right
        manual move — verify the field is writable from the standard path."""
        product = self.env.ref("southbrook_hardware_catalog.hw_blum_clip_top_blumotion_110")
        self.assertTrue(product.x_pricing_pending)
        product.x_pricing_pending = False
        self.assertFalse(product.x_pricing_pending)
