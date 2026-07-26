# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_mathw")
class TestInstall(TransactionCase):
    def test_client_action_exists(self):
        action = self.env.ref(
            "sb_materials_hardware.action_materials_hardware_catalog")
        self.assertEqual(action.tag, "sb_materials_hardware.catalog")
        self.assertEqual(action.target, "current")

    def test_menu_exists(self):
        menu = self.env.ref(
            "sb_materials_hardware.menu_materials_hardware_catalog")
        self.assertTrue(menu.action)
