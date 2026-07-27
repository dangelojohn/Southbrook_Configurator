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

    def test_suggested_purchase_uom_id_matches_seller_uom(self):
        """M-5: suggested_purchase_uom_id must be the WINNING seller's
        product_uom_id (product.supplierinfo), not some other fallback,
        when a seller resolves.
        """
        line = self._setup(demand=5.0, waste_pct=12.0, yield_qty=2.97)
        seller = line.product_id._select_seller()
        self.assertTrue(seller, "a seller must resolve for this fixture")
        expected_uom = seller.product_uom_id or line.product_id.uom_id
        self.assertEqual(line.suggested_purchase_uom_id, expected_uom)

    def test_post_yield_edit_recomputes_without_touching_product(self):
        """Locks I-1: entering the (net-new) vendor yield on an EXISTING
        product.supplierinfo — the feature's core post-deploy data-entry
        step — must retrigger `suggested_purchase_qty` on its own, via the
        @api.depends graph. This test deliberately does NOT call
        `_compute_suggested_purchase_qty()` manually and does NOT touch
        `product_id` after the initial setup — only the seller's
        `uom_yield_qty` is written. Pre-fix (depends missing
        `product_id.seller_ids.uom_yield_qty`), the stored value never
        recomputes and stays 0.0 forever.
        """
        fam = self.env["material.family"].create({"name": "EW", "code": "ew_sp_yld"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Sheet Yld", "code": "sheet_sp_yld", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05,
        })
        vendor = self.env["res.partner"].create({"name": "V Yld"})
        comp = self.env["product.product"].create(
            {"name": "Comp SP Yld", "purchase_method": "purchase"}
        )
        comp.product_tmpl_id.material_id = mat.id
        seller = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id, "product_tmpl_id": comp.product_tmpl_id.id,
            "price": 40.0, "uom_yield_qty": 0.0,
        })
        tmpl = self.env["product.template"].create({"name": "Cab SP Yld"})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": tmpl.product_variant_id.id,
        })
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0,
        })
        line.material_demand_qty = 5.0

        # yield=0 -> no suggestion yet (normal compute, first read).
        self.assertEqual(line.suggested_purchase_qty, 0.0)

        # Enter the net-new yield on the EXISTING seller — do NOT touch
        # product_id and do NOT call the compute method manually.
        seller.write({"uom_yield_qty": 2.97})

        self.assertGreater(
            line.suggested_purchase_qty, 0.0,
            "suggested_purchase_qty went stale after editing seller "
            "uom_yield_qty — @api.depends is missing the seller fields "
            "(I-1)",
        )

    def test_yield_suggestion_uom_is_units_not_product_stocking_uom(self):
        """Fix (2026-07-26): a yield-based suggestion is a COUNT of purchase
        units, so it must display in Units — NOT the product's own stocking
        UoM when that isn't Units (live: sheet goods stocked in m² showed a
        misleading 'order 1 m²'). Mirror that with a non-Units stocking UoM.
        """
        units = self.env.ref("uom.product_uom_unit")
        area = self.env.ref("uom.product_uom_kgm")  # any non-Units UoM stands in for m²
        fam = self.env["material.family"].create({
            "name": "EW2", "code": "ew_sp2", "default_waste_pct": 12.0})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Sheet2", "code": "sheet_sp2", "family_id": fam.id,
            "density": 0.68, "weight_source": "density_volume", "thickness_mm": 19.05})
        vendor = self.env["res.partner"].create({"name": "V2"})
        comp = self.env["product.product"].create({
            "name": "Comp SP2", "purchase_method": "purchase", "uom_id": area.id})
        comp.product_tmpl_id.material_id = mat.id
        self.env["product.supplierinfo"].create({
            "partner_id": vendor.id, "product_tmpl_id": comp.product_tmpl_id.id,
            "price": 40.0, "uom_yield_qty": 2.97})  # product_uom_id mirrors stocking UoM
        tmpl = self.env["product.template"].create({"name": "Cab SP2"})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": tmpl.product_variant_id.id})
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0})
        line.material_demand_qty = 5.0
        line._compute_suggested_purchase_qty()
        self.assertEqual(line.suggested_purchase_qty, 2.0)
        self.assertEqual(line.suggested_purchase_uom_id, units,
                         "yield-count suggestion must be in Units, not the m²-like stocking UoM")
        self.assertNotEqual(line.suggested_purchase_uom_id, area)
