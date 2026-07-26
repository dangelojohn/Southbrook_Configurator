# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material", "sb_geo")
class TestMaterialSeedData(TransactionCase):
    """Task C3: starter catalog seeded by data/material_seed_data.xml.

    Proves the fresh-install seed actually lights up the geometry-writeback
    weight calc: family_id -> effective_density > 0, thickness_mm at the
    standard value, thickness_in derived (dual-unit), and standard 4x8ft
    sheet dims on the sheet goods.
    """

    def setUp(self):
        super().setUp()
        self.mat_mdf_34 = self.env.ref("sb_material_core.mat_mdf_34")
        self.mat_ply_12 = self.env.ref("sb_material_core.mat_ply_12")

    def test_mat_mdf_34_family_density_and_dims(self):
        m = self.mat_mdf_34
        self.assertTrue(m.family_id)
        self.assertGreater(m.effective_density, 0.0)
        self.assertEqual(m.thickness_mm, 19.05)
        self.assertAlmostEqual(m.thickness_in, 19.05 / 25.4, delta=0.001)
        self.assertEqual(m.sheet_width_mm, 1219.2)
        self.assertEqual(m.sheet_height_mm, 2438.4)

    def test_mat_ply_12_family_density_and_dims(self):
        m = self.mat_ply_12
        self.assertTrue(m.family_id)
        self.assertGreater(m.effective_density, 0.0)
        self.assertEqual(m.thickness_mm, 12.70)
        self.assertAlmostEqual(m.thickness_in, 12.70 / 25.4, delta=0.001)
        self.assertEqual(m.sheet_width_mm, 1219.2)
        self.assertEqual(m.sheet_height_mm, 2438.4)
