# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "kitchenforge", "marathon")
class TestRebate(TransactionCase):

    def test_compute_amount(self):
        rec = self.env["kitchenforge.marathon.rebate"].new({
            "cabinet_count": 5,
            "rate_per_cabinet_usd": 8.0,
            "sale_order_id": self.env["sale.order"].search([], limit=1).id,
        })
        rec._compute_amount()
        self.assertEqual(rec.amount_usd, 40.0)

    def test_idempotent_credit(self):
        SO = self.env["sale.order"]
        Partner = self.env["res.partner"].create({"name": "Rebate Test"})
        cabinet = self.env["product.template"].create({
            "name": "Test Cab", "type": "consu", "config_ok": True,
        })
        so = SO.create({
            "partner_id": Partner.id,
            "order_line": [(0, 0, {
                "product_id": cabinet.product_variant_id.id,
                "product_uom_qty": 3,
            })],
        })
        Rebate = self.env["kitchenforge.marathon.rebate"]
        r1 = Rebate.credit_for_sale(so)
        r2 = Rebate.credit_for_sale(so)
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(r1.cabinet_count, 3)
