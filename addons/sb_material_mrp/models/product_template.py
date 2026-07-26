# SPDX-License-Identifier: LGPL-3.0-only
"""Buy-route helper (Phase-2 Task 5).

Assist-only: this button configures the NATIVE Odoo procurement route on
the product so the native MRP/replenishment scheduler is *permitted* to
buy the component. It does NOT create a purchase order, a purchase
requisition, or any procurement -- it only adds a route.

The native "Buy" route xml_id is grep-verified against the installed
Odoo 19 CE core (/Users/naadmin/Downloads/Official/V19C/odoo):

    addons/purchase_stock/data/purchase_stock_data.xml:
        <record id="route_warehouse0_buy" model='stock.route'>

i.e. the record lives in the `purchase_stock` module, NOT `stock` --
`stock.route_warehouse0_buy` does not exist in this core; the correct
external id is `purchase_stock.route_warehouse0_buy`. `purchase_stock`
is `auto_install: True` (depends on `stock_account` + `purchase`), and
is guaranteed present once `sb_material_mrp` is installed: `mrp` pulls
in `stock`, `purchase` pulls in `account`, `stock_account` auto-installs
from `stock`+`account`, and `purchase_stock` auto-installs from
`stock_account`+`purchase`. `raise_if_not_found=False` is kept as a
defensive guard regardless.
"""
from odoo import _, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def action_sb_set_route_buy(self):
        """Add the native Buy route to these products so the native
        scheduler can procure them (assist-only: this configures native
        procurement, it does NOT create POs). Idempotent."""
        buy = self.env.ref(
            "purchase_stock.route_warehouse0_buy", raise_if_not_found=False
        )
        if not buy:
            return False
        for tmpl in self:
            if buy.id not in tmpl.route_ids.ids:
                tmpl.route_ids = [(4, buy.id)]
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("Buy route set on %s product(s).", len(self)),
                "sticky": False,
            },
        }
