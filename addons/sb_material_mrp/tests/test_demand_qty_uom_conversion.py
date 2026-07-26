# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestDemandQtyUomConversion(TransactionCase):
    def _line_with_demand(self, weight_source, demand_qty):
        fam = self.env["material.family"].create({"name": "UC", "code": "uc_test"})
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "UC Mat", "code": "uc_mat", "family_id": fam.id,
            "density": 0.68, "weight_source": weight_source, "thickness_mm": 19.05,
        })
        tmpl = self.env["product.template"].create({"name": "Cab UC"})
        comp = self.env["product.product"].create({"name": "Comp UC"})
        comp.product_tmpl_id.material_id = mat.id
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": tmpl.id, "product_id": tmpl.product_variant_id.id})
        line = self.env["mrp.bom.line"].create({
            "bom_id": bom.id, "product_id": comp.id, "product_qty": 1.0})
        line.material_demand_qty = demand_qty  # force a known value
        return line

    def test_area_family_converts_to_square_feet(self):
        line = self._line_with_demand("density_volume", 2.0)
        sqft = self.env.ref("uom.product_uom_square_foot")
        qty, is_exact = line._sb_demand_qty_in_uom(sqft)
        self.assertTrue(is_exact)
        self.assertAlmostEqual(qty, 21.5278, places=3)  # 2 m2 in ft2

    def test_linear_family_converts_to_feet(self):
        line = self._line_with_demand("linear_density", 3.0)
        ft = self.env.ref("uom.product_uom_foot")
        qty, is_exact = line._sb_demand_qty_in_uom(ft)
        self.assertTrue(is_exact)
        self.assertAlmostEqual(qty, 9.8425, places=3)  # 3 m in ft

    def test_incompatible_target_uom_is_honest_fallback(self):
        line = self._line_with_demand("density_volume", 2.0)
        kg = self.env.ref("uom.product_uom_kgm")
        qty, is_exact = line._sb_demand_qty_in_uom(kg)
        self.assertFalse(is_exact)
        self.assertEqual(qty, 2.0)
