# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestMaterialFields(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Mat = self.env["southbrook.kitchen.material"]
        self.fam_ply = self.env.ref("sb_material_core.fam_ewood_ply")

    def test_effective_density_uses_own_value(self):
        m = self.Mat.create({"name": "Walnut Ply 18", "code": "WPL18",
                             "family_id": self.fam_ply.id, "density": 0.65,
                             "density_source": "material"})
        self.assertEqual(m.effective_density, 0.65)

    def test_effective_density_falls_back_to_family_default(self):
        # family default density lives on family via a fallback map; when the
        # material has none and density_source=family_default, effective!=0
        m = self.Mat.create({"name": "Generic Ply", "code": "GPL",
                             "family_id": self.fam_ply.id, "density": 0.0,
                             "density_source": "family_default"})
        self.assertGreater(m.effective_density, 0.0)
