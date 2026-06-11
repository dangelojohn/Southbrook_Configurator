# SPDX-License-Identifier: LGPL-3.0-only
"""M1 work-center sanity — the x_sbk_* fields exist on mrp.workcenter,
the 2 new work centers (ENG01, CNC02) land, station_type is applied
to all 12 existing Southbrook work centers, and bottleneck flags
reflect the brief §5 specification."""
from odoo.tests.common import TransactionCase, tagged


# Expected station_type per work-center xml_id (12 existing + 2 new).
# This is the contract M2's operation-template engine reads from when
# routing operations to work centers.
EXPECTED_STATION_TYPE_BY_XMLID = {
    # Existing 12 from southbrook_mrp_pm.
    "southbrook_mrp_pm.workcenter_saw":      "cutting",
    "southbrook_mrp_pm.workcenter_edge":     "edge_banding",
    "southbrook_mrp_pm.workcenter_cnc_bore": "cnc",
    "southbrook_mrp_pm.workcenter_assy":     "assembly",
    "southbrook_mrp_pm.workcenter_door":     "assembly",
    "southbrook_mrp_pm.workcenter_hw":       "hardware",
    "southbrook_mrp_pm.workcenter_qc":       "quality",
    "southbrook_mrp_pm.workcenter_pack":     "packing",
    "southbrook_mrp_pm.wc_door_shop":        "cnc",
    "southbrook_mrp_pm.wc_sand":             "sanding",
    "southbrook_mrp_pm.wc_paint":            "finishing",
    "southbrook_mrp_pm.wc_cure":             "finishing",
    # New from this module.
    "southbrook_mrp_kitchen_workcenters.wc_engineering":  "engineering",
    "southbrook_mrp_kitchen_workcenters.wc_cnc_router_02": "cnc",
}


# Per brief §5 — the bottleneck flag posture for the kitchen shop.
EXPECTED_BOTTLENECKS = {
    "southbrook_mrp_pm.workcenter_saw":      True,
    "southbrook_mrp_pm.workcenter_edge":     True,
    "southbrook_mrp_pm.workcenter_cnc_bore": True,
    "southbrook_mrp_pm.workcenter_assy":     True,
    "southbrook_mrp_pm.workcenter_qc":       True,
    "southbrook_mrp_pm.wc_paint":            True,
    # Explicitly non-bottleneck — sanity-check the others stay False.
    "southbrook_mrp_pm.workcenter_door":     False,
    "southbrook_mrp_pm.workcenter_hw":       False,
    "southbrook_mrp_pm.workcenter_pack":     False,
    "southbrook_mrp_pm.wc_door_shop":        False,
    "southbrook_mrp_pm.wc_sand":             False,
    "southbrook_mrp_pm.wc_cure":             False,
    "southbrook_mrp_kitchen_workcenters.wc_engineering":   False,
    "southbrook_mrp_kitchen_workcenters.wc_cnc_router_02": False,
}


@tagged("post_install", "-at_install", "southbrook", "sbk_kitchen", "m1")
class TestWorkcenterFields(TransactionCase):

    def test_x_sbk_fields_exist_on_workcenter(self):
        """Every field added by this module must be queryable."""
        Workcenter = self.env["mrp.workcenter"]
        expected_fields = (
            "x_sbk_station_type",
            "x_sbk_machine_code",
            "x_sbk_machine_brand",
            "x_sbk_supported_material_ids",
            "x_sbk_supported_finish_ids",
            "x_sbk_required_skill_ids",
            "x_sbk_max_panel_length_mm",
            "x_sbk_max_panel_width_mm",
            "x_sbk_default_setup_time_min",
            "x_sbk_changeover_time_min",
            "x_sbk_allows_parallel_jobs",
            "x_sbk_is_bottleneck",
            "x_sbk_oee_target",
            "x_sbk_planning_notes",
            "x_sbk_shop_floor_notes",
            "x_sbk_quality_notes",
            "x_sbk_active_for_kitchen",
        )
        for name in expected_fields:
            self.assertIn(
                name, Workcenter._fields,
                f"mrp.workcenter is missing field {name!r}",
            )

    def test_two_new_workcenters_seeded(self):
        for xml_id, station_type in (
            ("wc_engineering", "engineering"),
            ("wc_cnc_router_02", "cnc"),
        ):
            wc = self.env.ref(
                f"southbrook_mrp_kitchen_workcenters.{xml_id}",
                raise_if_not_found=False,
            )
            self.assertTrue(wc, f"{xml_id} not seeded")
            self.assertEqual(wc.x_sbk_station_type, station_type)
            self.assertTrue(wc.x_sbk_active_for_kitchen)

    def test_station_types_applied_to_all_workcenters(self):
        """Every work center named in the brief carries a station_type."""
        for xml_id, expected_type in EXPECTED_STATION_TYPE_BY_XMLID.items():
            wc = self.env.ref(xml_id, raise_if_not_found=False)
            self.assertTrue(wc, f"{xml_id} not found")
            self.assertEqual(
                wc.x_sbk_station_type, expected_type,
                f"{xml_id}: expected station_type={expected_type}, "
                f"got {wc.x_sbk_station_type}",
            )

    def test_bottlenecks_flagged_per_brief(self):
        for xml_id, expected_bottleneck in EXPECTED_BOTTLENECKS.items():
            wc = self.env.ref(xml_id)
            self.assertEqual(
                wc.x_sbk_is_bottleneck, expected_bottleneck,
                f"{xml_id}: expected bottleneck={expected_bottleneck}, "
                f"got {wc.x_sbk_is_bottleneck}",
            )

    def test_cnc_alternate_workcenter_linked(self):
        """CNC02 declares CNC-BORE as its alternate; CNC-BORE declares
        CNC02 back. The alternative_workcenter_ids reciprocity lets
        Odoo's scheduler swap them under load."""
        cnc_bore = self.env.ref("southbrook_mrp_pm.workcenter_cnc_bore")
        cnc02 = self.env.ref(
            "southbrook_mrp_kitchen_workcenters.wc_cnc_router_02")
        self.assertIn(cnc_bore, cnc02.alternative_workcenter_ids)
        self.assertIn(cnc02, cnc_bore.alternative_workcenter_ids)
