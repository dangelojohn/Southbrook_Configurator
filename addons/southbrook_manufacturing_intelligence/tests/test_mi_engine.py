# SPDX-License-Identifier: LGPL-3.0-only
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestManufacturingIntelligenceEngine(TransactionCase):
    def test_status_from_checks(self):
        Engine = self.env["southbrook.mi.engine"]
        self.assertEqual(Engine._status_from_severities([]), "ok")
        self.assertEqual(Engine._status_from_severities(["info"]), "ok")
        self.assertEqual(Engine._status_from_severities(["warning"]), "review")
        self.assertEqual(
            Engine._status_from_severities(["warning", "blocker"]), "blocked"
        )

    def test_stage_values_include_stage_gate_sequence_and_workcenter(self):
        Engine = self.env["southbrook.mi.engine"]
        workcenter = self.env["mrp.workcenter"].create({"name": "Panel Saw"})
        values = Engine._stage_values(
            "saw",
            10,
            is_gate=True,
            workcenter=workcenter,
        )
        self.assertEqual(values["stage"], "saw")
        self.assertEqual(values["sequence"], 10)
        self.assertTrue(values["is_gate"])
        self.assertEqual(values["workcenter_id"], workcenter.id)

    def test_stage_rollup_uses_first_blocked_stage_by_sequence(self):
        Engine = self.env["southbrook.mi.engine"]
        Check = self.env["southbrook.mi.check"]
        install = Check.create(
            {
                "name": "Install blocker",
                "severity": "blocker",
                "category": "install",
                "stage": "install",
                "sequence": 70,
                "message": "Install blocked",
                "recommendation": "Fix install",
            }
        )
        saw = Check.create(
            {
                "name": "Saw blocker",
                "severity": "blocker",
                "category": "cut",
                "stage": "saw",
                "sequence": 10,
                "message": "Saw blocked",
                "recommendation": "Fix saw",
            }
        )
        warning = Check.create(
            {
                "name": "Assembly warning",
                "severity": "warning",
                "category": "assembly",
                "stage": "assembly",
                "sequence": 40,
                "message": "Assembly review",
                "recommendation": "Review assembly",
            }
        )
        rollup = Engine._stage_rollup_from_checks(install | saw | warning)
        self.assertEqual(rollup["x_mi_blocked_stage"], "saw")
        self.assertEqual(rollup["x_mi_next_stage_action"], "Fix saw")
        self.assertEqual(rollup["x_mi_saw_blocker_count"], 1)
        self.assertEqual(rollup["x_mi_install_blocker_count"], 1)
        self.assertEqual(rollup["x_mi_assembly_blocker_count"], 0)

    def test_existing_checks_are_stage_aware(self):
        Engine = self.env["southbrook.mi.engine"]
        cut = Engine._cut_checks_from_panels(
            [
                {
                    "panel_name": "Tall pantry side",
                    "qty": 1,
                    "length_mm": 3000,
                    "width_mm": 1300,
                    "thickness_mm": 19,
                    "substrate": "plywood",
                    "grain_dir": "length",
                }
            ],
            {"waste_area_m2": 0.2},
        )
        hardware = Engine._hardware_checks_from_summary(None)
        install = Engine._install_checks_from_dimensions(900, 2400, 650)
        self.assertEqual(cut[0]["stage"], "saw")
        self.assertEqual(cut[0]["sequence"], 10)
        self.assertTrue(cut[0]["is_gate"])
        self.assertEqual(hardware[0]["stage"], "assembly")
        self.assertEqual(hardware[0]["sequence"], 40)
        self.assertEqual(
            [check["stage"] for check in install],
            ["install", "install", "install"],
        )

    def test_cut_summary(self):
        Engine = self.env["southbrook.mi.engine"]
        summary = Engine._compute_cut_summary(
            [
                {
                    "panel_name": "Side",
                    "qty": 2,
                    "length_mm": 700,
                    "width_mm": 600,
                    "thickness_mm": 19,
                    "substrate": "plywood",
                    "grain_dir": "length",
                    "edge_banding_config": {
                        "front": True,
                        "back": True,
                        "left": True,
                        "right": True,
                    },
                }
            ]
        )
        self.assertEqual(summary["sheet_count"], 1)
        self.assertGreater(summary["yield_pct"], 27)
        self.assertLess(summary["yield_pct"], 29)
        self.assertEqual(summary["duplicate_groups"][0]["qty"], 2)
        self.assertAlmostEqual(summary["edge_band_m"], 5.2)

    def test_cut_summary_respects_edge_banding_config(self):
        Engine = self.env["southbrook.mi.engine"]
        summary = Engine._compute_cut_summary(
            [
                {
                    "panel_name": "Top",
                    "qty": 1,
                    "length_mm": 600,
                    "width_mm": 300,
                    "thickness_mm": 19,
                    "edge_banding_config": '{"front": true}',
                }
            ]
        )
        self.assertAlmostEqual(summary["edge_band_m"], 0.6)

    def test_cut_checks_block_oversized_panel(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._cut_checks_from_panels(
            [
                {
                    "panel_name": "Tall pantry side",
                    "qty": 1,
                    "length_mm": 3000,
                    "width_mm": 1300,
                    "thickness_mm": 19,
                    "substrate": "plywood",
                    "grain_dir": "length",
                }
            ],
            {"waste_area_m2": 0.0},
        )
        oversized = [check for check in checks if check["name"] == "Oversized panel"]
        self.assertEqual(len(oversized), 1)
        self.assertEqual(oversized[0]["severity"], "blocker")
        self.assertEqual(oversized[0]["category"], "cut")

    def test_cut_checks_warn_when_grain_panel_requires_rotation(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._cut_checks_from_panels(
            [
                {
                    "panel_name": "Finished end",
                    "qty": 1,
                    "length_mm": 1000,
                    "width_mm": 2300,
                    "thickness_mm": 19,
                    "substrate": "veneer",
                    "grain_dir": "length",
                }
            ],
            {"waste_area_m2": 0.0},
        )
        grain = [
            check
            for check in checks
            if check["name"] == "Grain direction rotation review"
        ]
        self.assertEqual(len(grain), 1)
        self.assertEqual(grain[0]["severity"], "warning")
        self.assertEqual(grain[0]["category"], "cut")

    def test_cut_checks_recommend_reusable_offcut_labeling(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._cut_checks_from_panels([], {"waste_area_m2": 0.2})
        offcut = [check for check in checks if check["name"] == "Reusable offcut"]
        self.assertEqual(len(offcut), 1)
        self.assertEqual(offcut[0]["severity"], "info")
        self.assertEqual(offcut[0]["category"], "cut")

    def test_cut_batching_checks_recommend_batch_cutting_duplicates(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._cut_batching_checks_from_summary(
            {
                "duplicate_groups": [
                    {
                        "length_mm": 762,
                        "width_mm": 305,
                        "thickness_mm": 19,
                        "substrate": "melamine_white_5_8",
                        "grain_dir": "no_grain",
                        "qty": 6,
                    }
                ]
            }
        )
        batch = [check for check in checks if check["name"] == "Batch cut duplicate panels"]
        self.assertEqual(len(batch), 1)
        self.assertEqual(batch[0]["severity"], "info")
        self.assertEqual(batch[0]["category"], "cut")

    def test_edgeband_checks_warn_on_malformed_edge_config(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._edgeband_checks_from_panels(
            [
                {
                    "panel_name": "Door",
                    "qty": 1,
                    "length_mm": 700,
                    "width_mm": 400,
                    "thickness_mm": 19,
                    "edge_banding_config": "{bad json",
                }
            ],
            {"edge_band_m": 2.2},
        )
        malformed = [
            check for check in checks if check["name"] == "Edge banding config review"
        ]
        self.assertEqual(len(malformed), 1)
        self.assertEqual(malformed[0]["stage"], "edgeband")
        self.assertEqual(malformed[0]["severity"], "warning")

    def test_edgeband_checks_info_for_high_edge_band_length(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._edgeband_checks_from_panels([], {"edge_band_m": 45.0})
        staging = [
            check for check in checks if check["name"] == "Edge band material staging"
        ]
        self.assertEqual(len(staging), 1)
        self.assertEqual(staging[0]["stage"], "edgeband")
        self.assertEqual(staging[0]["severity"], "info")

    def test_assembly_checks_from_panels(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._assembly_checks_from_panels(
            [{"panel_name": "Adjustable Shelf", "length_mm": 950}]
        )
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["severity"], "warning")
        self.assertEqual(checks[0]["category"], "assembly")

    def test_material_handling_checks_warn_heavy_panel(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._material_handling_checks_from_panels(
            [
                {
                    "panel_name": "Island gable",
                    "qty": 1,
                    "length_mm": 2400,
                    "width_mm": 900,
                    "thickness_mm": 19,
                    "substrate": "melamine_white_5_8",
                }
            ]
        )
        heavy = [check for check in checks if check["name"] == "Two-person panel handling"]
        self.assertEqual(len(heavy), 1)
        self.assertEqual(heavy[0]["severity"], "warning")
        self.assertEqual(heavy[0]["category"], "assembly")

    def test_material_handling_checks_block_extreme_panel_weight(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._material_handling_checks_from_panels(
            [
                {
                    "panel_name": "Stone-look slab",
                    "qty": 1,
                    "length_mm": 3000,
                    "width_mm": 1200,
                    "thickness_mm": 25,
                    "substrate": "mdf_5_8",
                }
            ]
        )
        blocker = [
            check for check in checks if check["name"] == "Mechanical lift required"
        ]
        self.assertEqual(len(blocker), 1)
        self.assertEqual(blocker[0]["severity"], "blocker")
        self.assertEqual(blocker[0]["category"], "assembly")

    def test_hardware_checks_block_missing_package(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._hardware_checks_from_summary(None)
        missing = [
            check for check in checks if check["name"] == "Missing hardware package"
        ]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["severity"], "blocker")
        self.assertEqual(missing[0]["category"], "hardware")

    def test_hardware_checks_block_empty_pick_list(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._hardware_checks_from_summary(
            {"line_count": 0, "state": "draft", "has_pricing_pending": False}
        )
        empty = [check for check in checks if check["name"] == "Empty hardware pick list"]
        self.assertEqual(len(empty), 1)
        self.assertEqual(empty[0]["severity"], "blocker")
        self.assertEqual(empty[0]["category"], "hardware")

    def test_hardware_checks_warn_unresolved_pricing_and_draft_state(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._hardware_checks_from_summary(
            {"line_count": 3, "state": "draft", "has_pricing_pending": True}
        )
        self.assertEqual(
            len([check for check in checks if check["severity"] == "warning"]), 2
        )
        self.assertIn(
            "Hardware pricing pending", [check["name"] for check in checks]
        )
        self.assertIn(
            "Hardware not picked", [check["name"] for check in checks]
        )

    def test_install_checks_from_dimensions(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._install_checks_from_dimensions(600, 2400, 350)
        self.assertEqual(
            len([check for check in checks if check["severity"] == "warning"]), 1
        )
        self.assertEqual(
            len([check for check in checks if check["severity"] == "info"]), 1
        )

    def test_install_checks_warn_when_tip_up_clearance_is_high(self):
        Engine = self.env["southbrook.mi.engine"]
        checks = Engine._install_checks_from_dimensions(900, 2400, 650)
        tip_up = [
            check for check in checks if check["name"] == "Tip-up clearance review"
        ]
        self.assertEqual(len(tip_up), 1)
        self.assertEqual(tip_up[0]["severity"], "warning")
        self.assertEqual(tip_up[0]["category"], "install")

    def test_pdf_text_helper(self):
        warning = self.env["southbrook.mi.check"].create(
            {
                "name": "Tall cabinet install review",
                "severity": "warning",
                "category": "install",
                "message": "Cabinet height is 2400 mm.",
            }
        )
        lines = self.env["southbrook.mi.engine"]._install_check_lines_for_pdf(warning)
        self.assertEqual(
            lines[0],
            "Warning: Tall cabinet install review - Cabinet height is 2400 mm.",
        )
