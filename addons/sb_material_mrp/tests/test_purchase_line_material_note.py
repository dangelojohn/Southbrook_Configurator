# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestPurchaseLineMaterialNote(TransactionCase):
    def _setup_material_and_component(self, waste_pct, yield_qty=0.0):
        fam = self.env["material.family"].create(
            {"name": "PL", "code": "pl_test", "default_waste_pct": waste_pct})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "PL Mat", "code": "pl_mat", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05,
        })
        vendor = self.env["res.partner"].create({"name": "PL Vendor"})
        comp_tmpl = self.env["product.template"].create(
            {"name": "PL Comp", "is_storable": True, "purchase_ok": True})
        comp_tmpl.material_id = mat.id
        if yield_qty:
            self.env["product.supplierinfo"].create({
                "partner_id": vendor.id, "product_tmpl_id": comp_tmpl.id,
                "price": 40.0, "uom_yield_qty": yield_qty})
        return mat, vendor, comp_tmpl

    def _open_mo_demand(self, comp_tmpl, demand_qty=5.0):
        cab_tmpl = self.env["product.template"].create({"name": "PL Cab", "is_storable": True})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": cab_tmpl.id, "product_id": cab_tmpl.product_variant_id.id})
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp_tmpl.product_variant_id.id, "product_qty": 1.0})
        line.material_demand_qty = demand_qty
        mo = self.env["mrp.production"].create({
            "product_id": cab_tmpl.product_variant_id.id, "bom_id": bom.id, "product_qty": 1.0})
        mo.action_confirm()

    def _po_line(self, vendor, comp_tmpl):
        po = self.env["purchase.order"].create({"partner_id": vendor.id})
        return self.env["purchase.order.line"].create({
            "order_id": po.id, "product_id": comp_tmpl.product_variant_id.id,
            "product_qty": 1.0, "product_uom_id": comp_tmpl.uom_id.id,
            "price_unit": 40.0, "name": comp_tmpl.name,
        })

    def test_note_shows_yield_based_suggestion(self):
        mat, vendor, comp_tmpl = self._setup_material_and_component(waste_pct=12.0, yield_qty=2.97)
        self._open_mo_demand(comp_tmpl, demand_qty=5.0)
        line = self._po_line(vendor, comp_tmpl)
        self.assertGreater(line.sb_material_demand_qty, 0.0)
        self.assertIn("suggests", line.sb_material_suggested_note)

    def test_note_is_honest_when_no_yield_and_no_uom_match(self):
        mat, vendor, comp_tmpl = self._setup_material_and_component(waste_pct=12.0, yield_qty=0.0)
        self._open_mo_demand(comp_tmpl, demand_qty=5.0)
        line = self._po_line(vendor, comp_tmpl)
        # comp_tmpl.uom_id defaults to Units, which shares no reference
        # with the canonical m2 unit -> honest fallback, no suggestion
        self.assertIn("No vendor yield", line.sb_material_suggested_note)

    def test_no_material_no_demand_gives_empty_note(self):
        vendor = self.env["res.partner"].create({"name": "PL Vendor2"})
        comp_tmpl = self.env["product.template"].create(
            {"name": "PL Comp2", "is_storable": True, "purchase_ok": True})
        line = self._po_line(vendor, comp_tmpl)
        self.assertEqual(line.sb_material_suggested_note, "")
        self.assertEqual(line.sb_material_demand_qty, 0.0)
