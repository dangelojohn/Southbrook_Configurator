# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestCostCascade(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Src = self.env["material.cost.source"]
        self.vendor = self.env["res.partner"].create({"name": "Acme Ply Co"})
        self.prod = self.env["product.product"].create({"name": "Walnut Ply", "type": "consu"})

    def test_vendor_tier_wins_when_supplierinfo_exists(self):
        self.env["product.supplierinfo"].create(
            {"partner_id": self.vendor.id, "product_tmpl_id": self.prod.product_tmpl_id.id,
             "price": 92.0})
        res = self.Src._resolve(self.prod, 1.0)
        self.assertEqual(res["tier"], "vendor")
        self.assertAlmostEqual(res["unit_price"], 92.0)
        self.assertIn("Acme", res["provenance"])

    def test_falls_to_online_when_nothing(self):
        res = self.Src._resolve(self.prod, 1.0)
        self.assertEqual(res["tier"], "online")
        self.assertEqual(res["unit_price"], 0.0)
