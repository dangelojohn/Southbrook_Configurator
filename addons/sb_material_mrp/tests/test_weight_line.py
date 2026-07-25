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
