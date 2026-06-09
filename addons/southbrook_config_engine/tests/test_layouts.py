# SPDX-License-Identifier: LGPL-3.0-only
"""End-to-end layout tests — the gate criteria for shipping Module 7
per G4 §8."""
import json

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "southbrook", "config_engine", "layouts")
class TestLayouts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Engine = cls.env["southbrook.config.engine"]
        cls.partner = cls.env["res.partner"].create({"name": "Layout test"})

    def _build_project(self, wall_segments, appliances, theme="signature"):
        """Set up a project ready for the engine: project + analysis
        (confirmed) + appliances (each confirmed)."""
        project = self.env["sb.kitchen.project"].create({
            "name": "Layout test",
            "partner_id": self.partner.id,
            "theme": theme,
        })
        raw = {
            "schema": "southbrook.gemini.room_analysis.v1",
            "room": {
                "sink_detected": False, "window_count": 0, "room_door_count": 0,
                "floor_area_m2_approx": 20.0, "ceiling_height_mm_approx": 2400,
                "wall_segments": wall_segments,
            },
            "appliances": [
                {"label": a["name"], "wall_segment_id": a["wall_segment_id"],
                 "kind": a["kind"]}
                for a in appliances
            ],
        }
        analysis = self.env["sb.kitchen.ai.analysis"].create({
            "project_id": project.id,
            "raw_response_json": json.dumps(raw),
        })
        analysis.action_confirm()
        project.ai_analysis_id = analysis

        for a in appliances:
            self.env["sb.kitchen.appliance"].create({
                "project_id": project.id,
                "name": a["name"],
                "appliance_type": a["kind"],
                "width_mm": a["width_mm"],
                "position_x": a["position_pct"],
                "requires_clearance_mm": a.get("clearance", 0),
                "confirmed_by_human": True,
            })
        return project

    def _assert_run_packs(self, run):
        """A valid run: cabinets + appliance slots span the wall within
        ±1 mm; no cabinet overlaps another or an appliance."""
        wall_length = run["length_mm"]
        spans = []
        for cab in run["cabinets"]:
            spans.append((cab["x_offset_mm"],
                          cab["x_offset_mm"] + cab["width_mm"]))
        for slot in run["appliance_slots"]:
            spans.append((slot["x_offset_mm"],
                          slot["x_offset_mm"] + slot["width_mm"]))
        spans.sort()
        # No negative overlap.
        for (a_start, a_end), (b_start, b_end) in zip(spans, spans[1:]):
            self.assertLessEqual(a_end - 1.0, b_start,
                                  f"Overlap between {a_end} and {b_start}")
        # Total span (cabinets + slots + appliances + fillers) covers the wall.
        if spans:
            self.assertLessEqual(abs(spans[-1][1] - wall_length), 1.5,
                                 f"Run does not span wall: end={spans[-1][1]} wall={wall_length}")

    # ------------------------------------------------------------------
    # 1. Galley — two parallel runs, no corners.
    # ------------------------------------------------------------------
    def test_galley_two_parallel_runs(self):
        project = self._build_project(
            wall_segments=[
                {"id": "wall_north", "length_mm_approx": 3600},
                {"id": "wall_south", "length_mm_approx": 3600},
            ],
            appliances=[
                {"name": "Stove", "kind": "stove", "wall_segment_id": "wall_north",
                 "position_pct": 0.5, "width_mm": 762, "clearance": 30},
                {"name": "Fridge", "kind": "fridge", "wall_segment_id": "wall_south",
                 "position_pct": 0.25, "width_mm": 762},
            ],
            theme="signature",
        )
        envelope = self.Engine.place_for_project(project)
        self.assertEqual(envelope["schema"], "southbrook.config_engine.v1")
        self.assertEqual(len(envelope["runs"]), 2)
        self.assertEqual(envelope["errors"], [])
        for run in envelope["runs"]:
            self._assert_run_packs(run)

    # ------------------------------------------------------------------
    # 2. L-shape — two runs joined by one corner.
    # ------------------------------------------------------------------
    def test_l_shape_two_walls(self):
        project = self._build_project(
            wall_segments=[
                {"id": "wall_north", "length_mm_approx": 4200},
                {"id": "wall_east", "length_mm_approx": 2400},
            ],
            appliances=[
                {"name": "Stove", "kind": "stove", "wall_segment_id": "wall_north",
                 "position_pct": 0.4, "width_mm": 762, "clearance": 30},
            ],
            theme="elegance",
        )
        envelope = self.Engine.place_for_project(project)
        self.assertEqual(envelope["errors"], [])
        self.assertEqual(len(envelope["runs"]), 2)

    # ------------------------------------------------------------------
    # 3. U-shape — three runs.
    # ------------------------------------------------------------------
    def test_u_shape_three_walls(self):
        project = self._build_project(
            wall_segments=[
                {"id": "wall_north", "length_mm_approx": 3600},
                {"id": "wall_east", "length_mm_approx": 2700},
                {"id": "wall_west", "length_mm_approx": 2700},
            ],
            appliances=[
                {"name": "Stove", "kind": "stove", "wall_segment_id": "wall_north",
                 "position_pct": 0.5, "width_mm": 762, "clearance": 30},
                {"name": "Sink", "kind": "sink", "wall_segment_id": "wall_east",
                 "position_pct": 0.5, "width_mm": 762},
            ],
            theme="contractor",
        )
        envelope = self.Engine.place_for_project(project)
        self.assertEqual(envelope["errors"], [])
        self.assertEqual(len(envelope["runs"]), 3)

    # ------------------------------------------------------------------
    # 4. Island — one wall + a free-standing island.
    # ------------------------------------------------------------------
    def test_island_wall_plus_island(self):
        project = self._build_project(
            wall_segments=[
                {"id": "wall_north", "length_mm_approx": 4200},
                {"id": "island", "length_mm_approx": 3000},
            ],
            appliances=[
                {"name": "Sink", "kind": "sink", "wall_segment_id": "island",
                 "position_pct": 0.5, "width_mm": 762},
            ],
            theme="signature",
        )
        envelope = self.Engine.place_for_project(project)
        self.assertEqual(envelope["errors"], [])

    # ------------------------------------------------------------------
    # 5. Peninsula — wall + perpendicular extension.
    # ------------------------------------------------------------------
    def test_peninsula_wall_plus_extension(self):
        project = self._build_project(
            wall_segments=[
                {"id": "wall_north", "length_mm_approx": 4800},
                {"id": "peninsula", "length_mm_approx": 1800},
            ],
            appliances=[
                {"name": "Stove", "kind": "stove", "wall_segment_id": "wall_north",
                 "position_pct": 0.65, "width_mm": 762, "clearance": 30},
            ],
            theme="contemporary",
        )
        envelope = self.Engine.place_for_project(project)
        self.assertEqual(envelope["errors"], [])

    # ------------------------------------------------------------------
    # Determinism — re-running on the same inputs yields the same plan.
    # ------------------------------------------------------------------
    def test_deterministic_rerun(self):
        project = self._build_project(
            wall_segments=[
                {"id": "wall_north", "length_mm_approx": 3000},
            ],
            appliances=[
                {"name": "Stove", "kind": "stove", "wall_segment_id": "wall_north",
                 "position_pct": 0.5, "width_mm": 762, "clearance": 30},
            ],
        )
        first = self.Engine.place_for_project(project)
        second = self.Engine.place_for_project(project)
        # Strip the design_option_id since it's None in both runs.
        self.assertEqual(first["runs"], second["runs"],
                         "Engine must be deterministic per G4 §9")
