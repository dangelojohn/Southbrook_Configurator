# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestSchedulerDraftRfq(TransactionCase):
    def _sheet_component_with_buy_route(self, name, vendor_name):
        """Shared boilerplate for both this file's tests: a purchasable,
        storable component with a vendor (price + min_qty, no
        uom_yield_qty -- these fixtures have no material_id, so demand is
        the case-1 pass-through and never needs yield conversion) and the
        native Buy route applied (Phase-2a `action_sb_set_route_buy` --
        zero PO-creation code, just a route flag the native scheduler
        reads). Returns (comp_tmpl, comp, vendor)."""
        vendor = self.env["res.partner"].create({"name": vendor_name})
        comp_tmpl = self.env["product.template"].create({
            "name": name, "is_storable": True, "purchase_ok": True,
        })
        comp = comp_tmpl.product_variant_id
        self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": comp_tmpl.id,
            "price": 40.0,
            "min_qty": 1.0,
        })
        comp_tmpl.action_sb_set_route_buy()
        return comp_tmpl, comp, vendor

    def test_orderpoint_plus_buy_route_yields_draft_po_via_native_scheduler(self):
        comp_tmpl, comp, vendor = self._sheet_component_with_buy_route(
            "Sheet RFQ Proof", "Sheet Vendor RFQ")

        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        # product_min_qty=1.0 (not 0.0): the native trigger check is the
        # STRICT `qty_forecast < product_min_qty` (float_compare) -- with
        # zero on-hand and zero reservation, a min of 0.0 would never fire.
        # This test hand-sets MIN/MAX to prove the scheduler MECHANICS in
        # isolation; `test_min_from_demand_triggers_draft_rfq_end_to_end`
        # below proves the same trigger fires off a MIN the sync action
        # itself derived from real open-MO demand (Fork-1 size-aware-
        # trigger plan, T1 `action_sb_sync_orderpoints` + this file's T2).
        self.env["stock.warehouse.orderpoint"].create({
            "product_id": comp.id,
            "location_id": wh.lot_stock_id.id,
            "warehouse_id": wh.id,
            "company_id": wh.company_id.id,
            "product_min_qty": 1.0,
            "product_max_qty": 5.0,
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

    # ------------------------------------------------------------------
    # Fork-1 Task 2 (2026-07-27 size-aware-trigger plan) -- end-to-end:
    # a SYNCED min (not a hand-set one, as above) drives the native
    # trigger. On-hand is 0 in this fixture, so forecast (0) < min fires
    # the trigger exactly as it does live once the T2 migration activates
    # the 6 real sheet components.
    # ------------------------------------------------------------------

    def test_min_from_demand_triggers_draft_rfq_end_to_end(self):
        comp_tmpl, comp, vendor = self._sheet_component_with_buy_route(
            "Sheet E2E Proof", "Sheet Vendor E2E")

        # Open-MO demand: a confirmed cabinet MO consumes this component
        # via its BoM -- no material_id set on the component, so
        # `_sb_open_mo_material_demand_for_orderpoint_max`'s case 1
        # (pass-through) applies: material_demand_qty == line.product_qty,
        # always resolved, no yield/UoM conversion needed. 1.0 unit/cabinet
        # * 2.0 cabinets confirmed = 2.0 units of open-MO demand.
        cab_tmpl = self.env["product.template"].create(
            {"name": "Cab E2E", "is_storable": True})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": cab_tmpl.id,
            "product_id": cab_tmpl.product_variant_id.id,
            "product_qty": 1.0,
        })
        self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0,
        })
        mo = self.env["mrp.production"].create({
            "product_id": cab_tmpl.product_variant_id.id,
            "bom_id": bom.id, "product_qty": 2.0,
        })
        mo.action_confirm()

        # THE point of this test: the orderpoint MIN comes from the sync
        # action reading real demand, not a hand-set literal.
        comp_tmpl.action_sb_sync_orderpoints()
        op = self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", comp.id)])
        self.assertEqual(len(op), 1)
        self.assertGreater(op.product_min_qty, 0.0)
        self.assertGreaterEqual(op.product_max_qty, op.product_min_qty)

        po_before = self.env["purchase.order"].search([
            ("partner_id", "=", vendor.id), ("state", "=", "draft")])
        self.assertFalse(po_before)

        # THE native scheduler -- zero PO-creation code of ours, same
        # mechanics proven by the test above, now fed by the synced MIN.
        self.env["stock.rule"].run_scheduler(use_new_cursor=False)

        po = self.env["purchase.order"].search([
            ("partner_id", "=", vendor.id), ("state", "=", "draft")])
        self.assertTrue(
            po, "native scheduler should have drafted an RFQ from the "
                "SYNCED min (open-MO demand), not a hand-set one")
        po_line = po.order_line.filtered(lambda l: l.product_id == comp)
        self.assertTrue(po_line)
        # >= 1 in purchase units -- component's own UoM IS the purchase
        # UoM here (case-1 pass-through, no material/yield conversion).
        self.assertGreaterEqual(po_line.product_qty, 1.0)
        # never auto-confirmed by this proof -- assist-only until Task 5
        self.assertEqual(po.state, "draft")
