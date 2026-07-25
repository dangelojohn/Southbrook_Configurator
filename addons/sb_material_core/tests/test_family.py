# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "sbk_material")
class TestFamily(TransactionCase):
    def test_taxonomy_seeded_and_nested(self):
        Fam = self.env["material.family"]
        ewood = self.env.ref("sb_material_core.fam_ewood")
        ply = self.env.ref("sb_material_core.fam_ewood_ply")
        self.assertEqual(ply.parent_id, ewood)
        self.assertEqual(ply.complete_name, "Engineered Wood / Plywood")
        # all 14 top-level families present
        self.assertGreaterEqual(Fam.search_count([("parent_id", "=", False)]), 14)
