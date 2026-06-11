# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestManufacturingIntelligenceViews(TransactionCase):
    def test_mo_view_has_intelligence_tab(self):
        view = self.env.ref(
            "southbrook_manufacturing_intelligence.view_mrp_production_form_mi"
        )
        arch = view.arch_db
        self.assertIn("manufacturing_intelligence", arch)
        self.assertIn("action_recompute_manufacturing_intelligence", arch)

    def test_package_view_has_intelligence_tab(self):
        view = self.env.ref(
            "southbrook_manufacturing_intelligence.view_sb_production_package_form_mi"
        )
        arch = view.arch_db
        self.assertIn("x_mi_edge_band_m", arch)
        self.assertIn("x_mi_install_warning_count", arch)

    def test_pm_kanban_has_intelligence_chip_marker(self):
        view = self.env.ref(
            "southbrook_manufacturing_intelligence.view_southbrook_pm_kanban_mi"
        )
        self.assertIn("o_sb_mi_chip", view.arch_db)
        self.assertIn("x_mi_workcenter_blocker_count", view.arch_db)
        self.assertIn("x_mi_workcenter_warning_count", view.arch_db)
