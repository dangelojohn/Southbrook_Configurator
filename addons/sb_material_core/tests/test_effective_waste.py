# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestEffectiveWaste(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Fam = self.env["material.family"]
        self.Mat = self.env["southbrook.kitchen.material"]

    def test_material_override_wins(self):
        fam = self.Fam.create({"name": "F", "code": "f_test", "default_waste_pct": 15.0})
        mat = self.Mat.create({"name": "M", "code": "m_ov", "family_id": fam.id, "waste_pct": 8.0})
        self.assertEqual(mat._effective_waste_pct(), 8.0)

    def test_falls_back_to_family_default(self):
        fam = self.Fam.create({"name": "F2", "code": "f_test2", "default_waste_pct": 12.0})
        mat = self.Mat.create({"name": "M2", "code": "m_fam", "family_id": fam.id})
        self.assertEqual(mat._effective_waste_pct(), 12.0)

    def test_walks_parent_family(self):
        parent = self.Fam.create({"name": "P", "code": "p_test", "default_waste_pct": 10.0})
        child = self.Fam.create({"name": "C", "code": "c_test", "parent_id": parent.id})
        mat = self.Mat.create({"name": "M3", "code": "m_walk", "family_id": child.id})
        self.assertEqual(mat._effective_waste_pct(), 10.0)

    def test_no_waste_anywhere_is_zero(self):
        fam = self.Fam.create({"name": "F3", "code": "f_none"})
        mat = self.Mat.create({"name": "M4", "code": "m_none", "family_id": fam.id})
        self.assertEqual(mat._effective_waste_pct(), 0.0)
