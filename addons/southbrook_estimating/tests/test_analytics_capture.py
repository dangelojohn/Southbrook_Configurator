# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the NF1 southbrook.order.analytics companion model + the
sale.order.action_confirm capture hook."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook")
class TestAnalyticsCapture(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Order = cls.env["sale.order"]
        cls.Analytics = cls.env["southbrook.order.analytics"]

    def test_01_capture_creates_companion_row(self):
        partner = self.Partner.create({"name": "Test Dealer", "channel": "dealer"})
        order = self.Order.create({"partner_id": partner.id})
        row = self.Analytics.capture(order)
        self.assertTrue(row)
        self.assertEqual(row.sale_order_id, order)
        self.assertEqual(row.channel, "dealer")
        self.assertEqual(row.dealer_id, partner)

    def test_02_capture_is_idempotent(self):
        """Re-running capture on the same order updates the existing row."""
        partner = self.Partner.create({"name": "Idem Partner", "channel": "retail"})
        order = self.Order.create({"partner_id": partner.id})
        row1 = self.Analytics.capture(order)
        row2 = self.Analytics.capture(order)
        self.assertEqual(row1, row2)
        rows = self.Analytics.search([("sale_order_id", "=", order.id)])
        self.assertEqual(len(rows), 1)

    def test_03_dealer_id_only_set_for_dealer_channel(self):
        retail_partner = self.Partner.create({"name": "Walk-in", "channel": "retail"})
        order = self.Order.create({"partner_id": retail_partner.id})
        row = self.Analytics.capture(order)
        self.assertFalse(row.dealer_id)

    def test_04_tradesperson_tier_relates_through(self):
        partner = self.Partner.create({
            "name": "Tier 3",
            "channel": "tradesperson",
            "tradesperson_tier": "3",
        })
        order = self.Order.create({"partner_id": partner.id})
        row = self.Analytics.capture(order)
        self.assertEqual(row.tradesperson_tier, "3")

    def test_05_phase4_fields_default_null(self):
        partner = self.Partner.create({"name": "Phase4 P", "channel": "retail"})
        order = self.Order.create({"partner_id": partner.id})
        row = self.Analytics.capture(order)
        self.assertEqual(row.nest_yield_pct, 0.0)
        self.assertFalse(row.production_start_at)
        self.assertFalse(row.production_end_at)

    def test_06_action_confirm_triggers_capture(self):
        """End-to-end: confirming a sale.order materialises an analytics row."""
        partner = self.Partner.create({"name": "Confirm P", "channel": "dealer"})
        order = self.Order.create({"partner_id": partner.id})
        # Need at least one product on the order so action_confirm has work.
        product = self.env["product.product"].create({
            "name": "Test Cabinet",
            "list_price": 500.0,
        })
        self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": product.id,
            "product_uom_qty": 1.0,
        })
        order.action_confirm()
        row = self.Analytics.search([("sale_order_id", "=", order.id)])
        self.assertEqual(len(row), 1)
        self.assertTrue(row.confirmed_at)
