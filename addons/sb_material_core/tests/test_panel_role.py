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
