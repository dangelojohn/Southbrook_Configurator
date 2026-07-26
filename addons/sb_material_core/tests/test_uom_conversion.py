# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestUomConversion(TransactionCase):
    def test_converts_within_shared_reference(self):
        sqm = self.env.ref("uom.product_uom_square_meter")
        sqft = self.env.ref("uom.product_uom_square_foot")
        qty, is_exact = sqm.sb_convert_demand_qty(1.0, sqft)
        self.assertTrue(is_exact)
        self.assertAlmostEqual(qty, 10.7639, places=3)  # 1 m2 in ft2

    def test_same_uom_is_passthrough(self):
        sqm = self.env.ref("uom.product_uom_square_meter")
        qty, is_exact = sqm.sb_convert_demand_qty(3.2, sqm)
        self.assertTrue(is_exact)
        self.assertEqual(qty, 3.2)

    def test_no_common_reference_is_honest_fallback(self):
        sqm = self.env.ref("uom.product_uom_square_meter")
        kg = self.env.ref("uom.product_uom_kgm")
        qty, is_exact = sqm.sb_convert_demand_qty(5.0, kg)
        self.assertFalse(is_exact)
        self.assertEqual(qty, 5.0)  # unchanged, never fabricated

    def test_missing_to_uom_is_honest_fallback(self):
        sqm = self.env.ref("uom.product_uom_square_meter")
        qty, is_exact = sqm.sb_convert_demand_qty(5.0, self.env["uom.uom"])
        self.assertFalse(is_exact)
        self.assertEqual(qty, 5.0)


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestMaterialCanonicalUom(TransactionCase):
    def _mat(self, code, weight_source):
        fam = self.env["material.family"].create({"name": code, "code": code})
        return self.env["southbrook.kitchen.material"].create({
            "name": code, "code": code, "family_id": fam.id,
            "weight_source": weight_source,
        })

    def test_density_volume_maps_to_square_meter(self):
        mat = self._mat("cu_dv", "density_volume")
        self.assertEqual(
            mat._sb_canonical_demand_uom(), self.env.ref("uom.product_uom_square_meter"))

    def test_linear_density_maps_to_meter(self):
        mat = self._mat("cu_ld", "linear_density")
        self.assertEqual(
            mat._sb_canonical_demand_uom(), self.env.ref("uom.product_uom_meter"))

    def test_per_unit_maps_to_units(self):
        mat = self._mat("cu_pu", "per_unit")
        self.assertEqual(
            mat._sb_canonical_demand_uom(), self.env.ref("uom.product_uom_unit"))
