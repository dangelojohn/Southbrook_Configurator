# SPDX-License-Identifier: LGPL-3.0-only
"""Phase-2 Task 5 -- Buy-route helper.

`stock.route_warehouse0_buy` does NOT exist in the installed Odoo 19 CE
core (grep-verified against /Users/naadmin/Downloads/Official/V19C/odoo):
the Buy route record is defined in `purchase_stock/data/
purchase_stock_data.xml` as `<record id="route_warehouse0_buy" model=
'stock.route'>`, i.e. under the `purchase_stock` module. The correct
external id is `purchase_stock.route_warehouse0_buy`.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestRouteBuyHelper(TransactionCase):
    def test_adds_buy_route_idempotently(self):
        buy = self.env.ref("purchase_stock.route_warehouse0_buy")
        tmpl = self.env["product.template"].create(
            {"name": "Sheet Buy T5", "type": "consu"}
        )
        tmpl.action_sb_set_route_buy()
        self.assertIn(buy.id, tmpl.route_ids.ids)
        # idempotent
        tmpl.action_sb_set_route_buy()
        self.assertEqual(tmpl.route_ids.ids.count(buy.id), 1)
