# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestWeightLine(TransactionCase):
    def test_density_volume_conversion(self):
        # 600 x 400 x 18 mm panel = 4_320_000 mm3; walnut ply 0.65 g/cm3
        # weight_kg = 0.65 * 4_320_000 / 1_000_000 = 2.808 -> 2.81 kg
        Mat = self.env["southbrook.kitchen.material"]
        m = Mat.create({"name": "WPL18", "code": "WPL18", "density": 0.65,
                        "weight_source": "density_volume"})
        line = self.env["mrp.bom.line"].new({})
        line.material_id = m  # test the pure helper directly
        w = line._weight_from_volume(m, 4_320_000.0)
        self.assertAlmostEqual(w, 2.81, places=2)

    def test_per_unit_source(self):
        Mat = self.env["southbrook.kitchen.material"]
        m = Mat.create({"name": "Hinge", "code": "HNG",
                        "weight_source": "per_unit", "weight_per_unit": 0.4})
        line = self.env["mrp.bom.line"].new({})
        self.assertAlmostEqual(line._weight_for_qty(m, 0.0, 2.0), 0.8, places=2)

    def test_density_volume_fractional_qty_half_up_rounding(self):
        """FIX-C (repair wave 1, finding #12) — the density_volume branch
        of `_weight_for_qty` must apply the SAME final HALF-UP 2dp round
        to its qty-multiplied result as the linear_density and per_unit
        branches already do. Before the fix, `_weight_for_qty` returned
        `_weight_from_volume(...) * qty` with no final rounding, so a
        fractional qty could reintroduce more than 2 decimal places
        (per-unit 2.81kg * 2.5 = 7.025, not the HALF-UP-2dp-correct
        7.03). volume=4_321_234mm3, density=0.65g/cm3 (per-unit raw =
        2.8088021 -> HALF-UP 2dp = 2.81), qty=2.5.
        """
        Mat = self.env["southbrook.kitchen.material"]
        m = Mat.create({"name": "WPL18-Frac", "code": "WPL18F",
                        "density": 0.65, "weight_source": "density_volume"})
        line = self.env["mrp.bom.line"].new({})
        line.material_id = m
        per_unit = line._weight_from_volume(m, 4_321_234.0)
        self.assertEqual(per_unit, 2.81, "sanity: per-unit HALF-UP round unchanged")
        result = line._weight_for_qty(m, 4_321_234.0, 2.5)
        self.assertEqual(
            result, 7.03,
            "density_volume branch must HALF-UP round the qty-multiplied "
            "total to 2dp, exactly like linear_density/per_unit do",
        )
