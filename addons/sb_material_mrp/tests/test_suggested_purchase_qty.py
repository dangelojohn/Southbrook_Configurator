# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestSuggestedPurchaseQty(TransactionCase):
    def _setup(self, demand, waste_pct, yield_qty):
        fam = self.env["material.family"].create({
            "name": "EW", "code": "ew_sp", "default_waste_pct": waste_pct})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Sheet", "code": "sheet_sp", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05})
        vendor = self.env["res.partner"].create({"name": "V"})
        comp = self.env["product.product"].create({"name": "Comp SP", "purchase_method": "purchase"})
        comp.product_tmpl_id.material_id = mat.id
        self.env["product.supplierinfo"].create({
            "partner_id": vendor.id, "product_tmpl_id": comp.product_tmpl_id.id,
            "price": 40.0, "uom_yield_qty": yield_qty})
        tmpl = self.env["product.template"].create({"name": "Cab SP"})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": tmpl.product_variant_id.id})
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0})
        # force a known demand independent of geometry for a deterministic assertion
        line.material_demand_qty = demand
        line._compute_suggested_purchase_qty()
        return line

    def test_ceiling_with_waste(self):
        # demand 5.0 m², 12% waste => 5.6; yield 2.97 m²/sheet => 1.885 => ceil 2
        line = self._setup(demand=5.0, waste_pct=12.0, yield_qty=2.97)
        self.assertEqual(line.suggested_purchase_qty, 2.0)

    def test_no_yield_no_suggestion(self):
        line = self._setup(demand=5.0, waste_pct=12.0, yield_qty=0.0)
        self.assertEqual(line.suggested_purchase_qty, 0.0)

    def test_zero_demand_no_suggestion(self):
        line = self._setup(demand=0.0, waste_pct=12.0, yield_qty=2.97)
        self.assertEqual(line.suggested_purchase_qty, 0.0)
