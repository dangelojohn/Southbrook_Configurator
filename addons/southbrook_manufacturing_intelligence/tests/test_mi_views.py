# SPDX-License-Identifier: LGPL-3.0-only
from lxml import etree

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

    def test_pm_kanban_intelligence_chips_use_record_values(self):
        view = self.env.ref(
            "southbrook_manufacturing_intelligence.view_southbrook_pm_kanban_mi"
        )
        arch = etree.fromstring(view.arch_db.encode())
        rendered_field_nodes = arch.xpath(
            ".//xpath[not(contains(@expr, '//kanban/field'))]//field"
        )

        self.assertFalse(
            rendered_field_nodes,
            "PM dashboard MI chips should avoid field widgets in the kanban "
            "card template; they can break when archInfo.fieldNodes is stale "
            "or incomplete.",
        )

    def test_manager_dashboard_views_load(self):
        for xmlid in [
            "southbrook_manufacturing_intelligence.view_southbrook_mi_check_list",
            "southbrook_manufacturing_intelligence.view_southbrook_mi_check_search",
            "southbrook_manufacturing_intelligence.view_southbrook_mi_package_list",
            "southbrook_manufacturing_intelligence.action_southbrook_mi_checks",
            "southbrook_manufacturing_intelligence.action_southbrook_mi_packages",
        ]:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False), xmlid)

        checks_action = self.env.ref(
            "southbrook_manufacturing_intelligence.action_southbrook_mi_checks"
        )
        checks_search = self.env.ref(
            "southbrook_manufacturing_intelligence.view_southbrook_mi_check_search"
        )
        self.assertEqual(checks_action.view_mode, "list")
        self.assertEqual(checks_action.search_view_id, checks_search)

        packages_action = self.env.ref(
            "southbrook_manufacturing_intelligence.action_southbrook_mi_packages"
        )
        package_list = self.env.ref(
            "southbrook_manufacturing_intelligence.view_southbrook_mi_package_list"
        )
        self.assertEqual(packages_action.view_mode, "list,form")
        self.assertEqual(packages_action.view_id, package_list)

        check_list = self.env.ref(
            "southbrook_manufacturing_intelligence.view_southbrook_mi_check_list"
        )
        for field_name in [
            "sequence",
            "stage",
            "severity",
            "is_gate",
            "category",
            "name",
            "production_package_id",
            "production_id",
            "workcenter_id",
            "message",
            "recommendation",
        ]:
            self.assertIn('name="%s"' % field_name, check_list.arch_db)

        for filter_name in [
            "blockers",
            "warnings",
            "gate_checks",
            "stage_saw",
            "stage_cnc",
            "stage_edgeband",
            "stage_assembly",
            "stage_finish_qc",
            "stage_delivery",
            "stage_install",
            "group_stage",
            "group_severity",
            "group_package",
            "group_workcenter",
        ]:
            self.assertIn('name="%s"' % filter_name, checks_search.arch_db)

        for field_name in ["x_mi_blocked_stage", "x_mi_next_stage_action"]:
            self.assertIn('name="%s"' % field_name, package_list.arch_db)
