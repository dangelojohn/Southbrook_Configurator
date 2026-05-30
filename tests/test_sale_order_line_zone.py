# SPDX-License-Identifier: LGPL-3.0-only
"""Tests for the Q21 + NF9 zone field on sale.order.line."""
from odoo.tests.common import tagged

from .common import SouthbrookTestCase


@tagged("post_install", "-at_install", "southbrook", "q21")
class TestSaleOrderLineZone(SouthbrookTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Q21 Partner",
            "channel": "dealer",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Q21 Test Product",
            "list_price": 100.0,
        })

    def _line(self, zone=None, zone_label=None):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        vals = {
            "order_id": order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
        }
        if zone is not None:
            vals["zone"] = zone
        if zone_label is not None:
            vals["zone_label"] = zone_label
        return self.env["sale.order.line"].create(vals)

    def test_01_default_zone_is_base_run(self):
        line = self._line()
        self.assertEqual(line.zone, "base_run")
        self.assertFalse(line.zone_label)

    def test_02_all_six_zones_accepted(self):
        for z in ("base_run", "wall", "tall", "island", "accessory", "other"):
            line = self._line(zone=z)
            self.assertEqual(line.zone, z)

    def test_03_zone_label_kept_for_other(self):
        line = self._line(zone="other", zone_label="Laundry")
        self.assertEqual(line.zone_label, "Laundry")

    def test_04_onchange_clears_label_when_leaving_other(self):
        """Setting zone away from 'other' via onchange clears zone_label."""
        from odoo.tests.common import Form
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        with Form(order) as f:
            with f.order_line.new() as line:
                line.product_id = self.product
                line.zone = "other"
                line.zone_label = "Mudroom"
                self.assertEqual(line.zone_label, "Mudroom")
                # Switch to a named zone — onchange should clear the label.
                line.zone = "wall"
                self.assertFalse(line.zone_label)
