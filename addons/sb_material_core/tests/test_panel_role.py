# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sbk_material", "sb_geo")
class TestPanelRole(TransactionCase):
    def test_seven_roles_seeded(self):
        Role = self.env["sb.panel.role"]
        codes = set(Role.search([]).mapped("code"))
        self.assertTrue(
            {"side_L", "side_R", "top", "bottom", "back", "shelf", "door"} <= codes)

    def test_material_panel_role_ids_assignable(self):
        back = self.env.ref("sb_material_core.panel_role_back")
        mat = self.env["southbrook.kitchen.material"].create({
            "name": "Test Back Mat", "code": "t_backmat",
            "panel_role_ids": [(6, 0, back.ids)]})
        self.assertEqual(mat.panel_role_ids.mapped("code"), ["back"])

    def test_seeded_back_material_has_back_role(self):
        back = self.env.ref("sb_material_core.mat_ply_14_back")
        self.assertIn("back", back.panel_role_ids.mapped("code"))

    def test_seeded_carcass_material_has_box_roles(self):
        mel = self.env.ref("sb_material_core.mat_melamine_34")
        self.assertTrue({"side_L", "side_R", "top", "bottom"}
                        <= set(mel.panel_role_ids.mapped("code")))
