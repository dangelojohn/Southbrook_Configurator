# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestSchedulerDraftRfq(TransactionCase):
    def test_orderpoint_plus_buy_route_yields_draft_po_via_native_scheduler(self):
        vendor = self.env["res.partner"].create({"name": "Sheet Vendor RFQ"})
        comp_tmpl = self.env["product.template"].create({
            "name": "Sheet RFQ Proof", "is_storable": True, "purchase_ok": True,
        })
        comp = comp_tmpl.product_variant_id
        self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": comp_tmpl.id,
            "price": 40.0,
            "min_qty": 1.0,
        })
        # Phase-2a Task 5: native Buy route -- zero PO-creation code, just a
        # route flag the native scheduler reads.
        comp_tmpl.action_sb_set_route_buy()

        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        # product_min_qty=1.0 (not 0.0): the native trigger check is the
        # STRICT `qty_forecast < product_min_qty` (float_compare) -- with
        # zero on-hand and zero reservation, a min of 0.0 would never fire.
        # This value simulates what Task 2's sync action would set once a
        # human also configures a real safety-stock MIN; Task 2 itself
        # never writes MIN (see the plan's architecture note).
        self.env["stock.warehouse.orderpoint"].create({
            "product_id": comp.id,
            "location_id": wh.lot_stock_id.id,
            "warehouse_id": wh.id,
            "company_id": wh.company_id.id,
            "product_min_qty": 1.0,
            "product_max_qty": 5.0,  # simulates Task 2's rollup-derived MAX
        })

        po_before = self.env["purchase.order"].search([
            ("partner_id", "=", vendor.id), ("state", "=", "draft")])
        self.assertFalse(po_before)

        # THE native scheduler -- zero PO-creation code in this test or in
        # any Southbrook module. `stock.rule` is the model that carries
        # `run_scheduler` in this v19 core (grep-verified: addons/stock/
        # models/stock_rule.py, class StockRule, _name = "stock.rule" --
        # NOT a separate "procurement.group" model as in older Odoo).
        self.env["stock.rule"].run_scheduler(use_new_cursor=False)

        po = self.env["purchase.order"].search([
            ("partner_id", "=", vendor.id), ("state", "=", "draft")])
        self.assertTrue(po, "native scheduler should have drafted an RFQ")
        self.assertIn(comp.id, po.order_line.mapped("product_id").ids)
        # never auto-confirmed by this proof -- assist-only until Task 5
        self.assertEqual(po.state, "draft")
