# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestSupplierinfoYield(TransactionCase):
    def test_uom_yield_qty_field_defaults_zero_and_stores(self):
        vendor = self.env["res.partner"].create({"name": "Sheet Vendor"})
        product = self.env["product.product"].create({"name": "Melamine Sheet"})
        seller = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.product_tmpl_id.id,
        })
        self.assertEqual(seller.uom_yield_qty, 0.0)
        seller.uom_yield_qty = 2.97
        self.assertAlmostEqual(seller.uom_yield_qty, 2.97, places=2)
