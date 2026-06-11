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

    def test_package_view_has_stage_gate_fields(self):
        view = self.env.ref(
            "southbrook_manufacturing_intelligence.view_sb_production_package_form_mi"
        )
        arch = view.arch_db
        self.assertIn("x_mi_blocked_stage", arch)
        self.assertIn("x_mi_next_stage_action", arch)
        self.assertIn("x_mi_saw_blocker_count", arch)
        self.assertIn("stage", arch)
        self.assertIn("is_gate", arch)

    def test_pm_kanban_has_intelligence_chip_marker(self):
        view = self.env.ref(
            "southbrook_manufacturing_intelligence.view_southbrook_pm_kanban_mi"
        )
        self.assertIn("o_sb_mi_chip", view.arch_db)
        self.assertIn("x_mi_workcenter_blocker_count", view.arch_db)
        self.assertIn("x_mi_workcenter_warning_count", view.arch_db)

    def test_manager_dashboard_views_load(self):
        for xmlid in [
            "southbrook_manufacturing_intelligence.view_southbrook_mi_check_list",
            "southbrook_manufacturing_intelligence.view_southbrook_mi_check_search",
            "southbrook_manufacturing_intelligence.view_southbrook_mi_package_list",
            "southbrook_manufacturing_intelligence.action_southbrook_mi_checks",
            "southbrook_manufacturing_intelligence.action_southbrook_mi_packages",
        ]:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False), xmlid)
