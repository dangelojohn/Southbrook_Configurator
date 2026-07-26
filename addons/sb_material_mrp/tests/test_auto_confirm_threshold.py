# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestAutoConfirmThreshold(TransactionCase):
    def _draft_rfq_via_scheduler(self, vendor_name, price=40.0, min_qty=1.0):
        vendor = self.env["res.partner"].create({"name": vendor_name})
        comp_tmpl = self.env["product.template"].create({
            "name": f"{vendor_name} Comp", "is_storable": True, "purchase_ok": True})
        comp = comp_tmpl.product_variant_id
        self.env["product.supplierinfo"].create({
            "partner_id": vendor.id, "product_tmpl_id": comp_tmpl.id,
            "price": price, "min_qty": min_qty})
        comp_tmpl.action_sb_set_route_buy()
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        self.env["stock.warehouse.orderpoint"].create({
            "product_id": comp.id, "location_id": wh.lot_stock_id.id,
            "warehouse_id": wh.id, "company_id": wh.company_id.id,
            "product_min_qty": 1.0, "product_max_qty": 2.0,
        })
        self.env["stock.rule"].run_scheduler(use_new_cursor=False)
        return self.env["purchase.order"].search([("partner_id", "=", vendor.id)], limit=1)

    def test_default_off_leaves_po_draft(self):
        self.env.company.sb_material_po_auto_confirm = False
        po = self._draft_rfq_via_scheduler("AutoConfirm Off Vendor")
        self.assertTrue(po)
        self.assertEqual(po.state, "draft")

    def test_enabled_under_threshold_auto_confirms(self):
        self.env.company.sb_material_po_auto_confirm = True
        self.env.company.sb_material_po_auto_confirm_max_amount = 1000.0
        po = self._draft_rfq_via_scheduler("AutoConfirm On Vendor", price=40.0, min_qty=1.0)
        self.assertTrue(po)
        self.assertEqual(po.state, "purchase")  # native button_confirm ran

    def test_enabled_over_threshold_stays_draft(self):
        self.env.company.sb_material_po_auto_confirm = True
        self.env.company.sb_material_po_auto_confirm_max_amount = 10.0
        po = self._draft_rfq_via_scheduler("AutoConfirm Over Vendor", price=999.0, min_qty=1.0)
        self.assertTrue(po)
        self.assertEqual(po.state, "draft")

    def test_zero_threshold_never_fires_even_if_enabled(self):
        self.env.company.sb_material_po_auto_confirm = True
        self.env.company.sb_material_po_auto_confirm_max_amount = 0.0
        po = self._draft_rfq_via_scheduler("AutoConfirm ZeroCeiling Vendor")
        self.assertEqual(po.state, "draft")

    def test_zero_amount_po_stays_draft_failsafe(self):
        # CRITICAL fail-safe: a $0.00 draft PO must never auto-confirm, even
        # with the feature ON and a real positive threshold -- 0.0 <= 1000.0
        # is otherwise True, so without the explicit lower-bound guard this
        # PO would be confirmed. Must stay draft for human review.
        self.env.company.sb_material_po_auto_confirm = True
        self.env.company.sb_material_po_auto_confirm_max_amount = 1000.0
        po = self._draft_rfq_via_scheduler(
            "AutoConfirm ZeroAmount Vendor", price=0.0, min_qty=1.0)
        self.assertTrue(po)
        self.assertEqual(po.amount_total, 0.0)
        self.assertEqual(po.state, "draft")

    def test_audit_trail_posted_exactly_once(self):
        # Exactly one audit trace per auto-confirm -- not zero (silent
        # auto-confirm) and not two (duplicate posting from a re-entrant
        # scheduler pass or a stray second call site).
        self.env.company.sb_material_po_auto_confirm = True
        self.env.company.sb_material_po_auto_confirm_max_amount = 1000.0
        po = self._draft_rfq_via_scheduler(
            "AutoConfirm Audit Vendor", price=40.0, min_qty=1.0)
        self.assertEqual(po.state, "purchase")
        audit_msgs = po.message_ids.filtered(
            lambda m: "Auto-confirmed by Southbrook Materials" in (m.body or "")
        )
        self.assertEqual(len(audit_msgs), 1)
