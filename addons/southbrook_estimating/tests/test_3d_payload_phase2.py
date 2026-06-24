# SPDX-License-Identifier: LGPL-3.0-only
"""Phase 2 (2026-06-24) — door style + handle geometry.

Covers the server-side 3D payload elaboration introduced in
addons/southbrook_estimating/models/product_config_line.py:

  - Slab door: 1 face panel (no regression vs Phase 1)
  - Five-piece door: 5 panels (inset + 4 frame rails)
  - Bar Pull / Knob / Cup Pull: 1 hardware-material panel per face
  - Integrated / None: no hardware panel
  - Drawer fronts: per-front face elaboration + per-front handle
"""
from .common import SouthbrookTestCase


class TestPhase23DPayload(SouthbrookTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ConfigSession = cls.env["product.config.session"]

    def _emit_doors_panels(self, door_style="slab", handle="none",
                           door_count=1, W=600, H=720, pull_finish=""):
        panels = []
        self.ConfigSession._emit_doors(
            panels=panels, W=W, H=H, y0=0, DOOR_TH=18, DOOR_REVEAL=3,
            door_count=door_count,
            door_style=door_style, handle=handle,
            pull_finish=pull_finish,
        )
        return panels

    def _emit_drawer_panels(self, door_style="slab", handle="none",
                            drawer_count=3, W=600, H=720, pull_finish=""):
        panels = []
        self.ConfigSession._emit_drawer_fronts(
            panels=panels, W=W, H=H, y0=0, DOOR_TH=18, DOOR_REVEAL=3,
            drawer_count=drawer_count,
            door_style=door_style, handle=handle,
            pull_finish=pull_finish,
        )
        return panels

    # ---------- Door style: slab vs five-piece ----------

    def test_slab_door_emits_single_panel(self):
        panels = self._emit_doors_panels(door_style="slab", handle="none")
        # Exactly 1 panel for a 1-door slab (no handle)
        self.assertEqual(len(panels), 1)
        self.assertEqual(panels[0]["material"], "door")

    def test_five_piece_door_emits_inset_plus_four_rails(self):
        panels = self._emit_doors_panels(door_style="five_piece", handle="none")
        # 1 inset + 4 rails = 5 panels
        self.assertEqual(len(panels), 5)
        names = {p["name"] for p in panels}
        self.assertIn("door_panel", names)
        self.assertIn("door_rail_top", names)
        self.assertIn("door_rail_bottom", names)
        self.assertIn("door_stile_L", names)
        self.assertIn("door_stile_R", names)

    def test_five_piece_tiny_door_falls_back_to_slab(self):
        # Door too small for a frame extrusion (< 2*FRAME on either axis)
        # falls back to a single slab panel. Keeps tiny accessory doors
        # from rendering as a single rail with no center.
        panels = self._emit_doors_panels(
            door_style="five_piece", handle="none",
            W=80, H=80,
        )
        self.assertEqual(len(panels), 1)
        self.assertEqual(panels[0]["material"], "door")

    def test_two_door_five_piece(self):
        panels = self._emit_doors_panels(
            door_style="five_piece", handle="none", door_count=2,
        )
        # 2 doors × 5 panels each = 10 panels
        self.assertEqual(len(panels), 10)

    # ---------- Handles ----------

    def test_pull_finish_drives_hardware_material(self):
        # Phase 2 Round 2.5: each Pull Finish maps to its dedicated
        # hardware_<slug> client material name.
        for finish, expected in [
            ("polished_nickel",   "hardware_polished_nickel"),
            ("matte_black",       "hardware_matte_black"),
            ("brushed_brass",     "hardware_brushed_brass"),
            ("oil_rubbed_bronze", "hardware_oil_rubbed_bronze"),
        ]:
            panels = self._emit_doors_panels(
                door_style="slab", handle="knob", pull_finish=finish,
            )
            hardware = [p for p in panels if "hardware" in (p.get("material") or "")]
            self.assertEqual(len(hardware), 1, f"finish={finish}")
            self.assertEqual(hardware[0]["material"], expected,
                             f"finish={finish}")

    def test_unknown_pull_finish_falls_back_to_generic_hardware(self):
        panels = self._emit_doors_panels(
            door_style="slab", handle="knob", pull_finish="some_unknown_finish",
        )
        hardware = [p for p in panels if "hardware" in (p.get("material") or "")]
        self.assertEqual(len(hardware), 1)
        self.assertEqual(hardware[0]["material"], "hardware")

    def test_empty_pull_finish_uses_generic_hardware(self):
        panels = self._emit_doors_panels(
            door_style="slab", handle="knob",
        )
        hardware = [p for p in panels if "hardware" in (p.get("material") or "")]
        self.assertEqual(len(hardware), 1)
        self.assertEqual(hardware[0]["material"], "hardware")

    def test_bar_pull_on_door_is_vertical_cylinder(self):
        # Phase 2 Round 2: bar pull is now a cylinder on the Y axis
        # (vertical) when on a door.
        panels = self._emit_doors_panels(door_style="slab", handle="bar_pull")
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 1)
        h = hardware[0]
        self.assertEqual(h.get("shape"), "cylinder")
        self.assertEqual(h.get("axis"), "y")

    def test_bar_pull_on_drawer_is_horizontal_cylinder(self):
        panels = self._emit_drawer_panels(
            door_style="slab", handle="bar_pull", drawer_count=1,
        )
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 1)
        h = hardware[0]
        self.assertEqual(h.get("shape"), "cylinder")
        self.assertEqual(h.get("axis"), "x")

    def test_knob_emits_sphere_shape(self):
        # Phase 2 Round 2: knob is a sphere; isometric dims so the
        # client SphereGeometry takes min/2 as radius.
        panels = self._emit_doors_panels(door_style="slab", handle="knob")
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 1)
        h = hardware[0]
        self.assertEqual(h.get("shape"), "sphere")
        d = h["dims"]
        self.assertEqual(d["width"], d["height"])
        self.assertEqual(d["height"], d["depth"])

    def test_integrated_handle_emits_no_hardware(self):
        panels = self._emit_doors_panels(door_style="slab", handle="integrated")
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 0)

    def test_none_handle_emits_no_hardware(self):
        panels = self._emit_doors_panels(door_style="slab", handle="none")
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 0)

    # ---------- Drawer fronts ----------

    def test_three_drawer_slab_emits_three_fronts(self):
        panels = self._emit_drawer_panels(
            door_style="slab", handle="none", drawer_count=3,
        )
        # 3 fronts × 1 face panel each (slab) = 3
        self.assertEqual(len(panels), 3)

    def test_three_drawer_five_piece_with_bar_pull(self):
        panels = self._emit_drawer_panels(
            door_style="five_piece", handle="bar_pull", drawer_count=3,
        )
        # Per drawer: 5 face panels + 1 handle = 6. Times 3 = 18.
        # H=720 / 3 fronts gives ~238mm per front — above 2*FRAME=120,
        # so the five_piece branch fires (not slab fallback).
        self.assertEqual(len(panels), 18)
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 3)

    # ---------- Finished sides material swap ----------

    def _build_payload(self, finished_sides, family="base",
                        crown_molding="none"):
        """Drive _cut_list_to_3d_payload with a synthetic cabinet
        + cut-list dict — covers panel emission that fires inside the
        full payload pipeline."""
        cab = {
            "width_mm": 600, "height_mm": 720, "depth_mm": 609,
            "family": family, "door_count": 1, "drawer_count": 0,
            "finished_sides": finished_sides,
            "door_style": "slab", "handle": "none",
            "crown_molding": crown_molding,
        }
        cut = {"shelf": None, "shelf_count": 0}
        payload = self.ConfigSession._cut_list_to_3d_payload(cab, cut)
        sides = {p["name"]: p for p in payload["panels"]
                 if p["name"] in ("side_L", "side_R")}
        return sides

    def _build_full_payload(self, **cab_overrides):
        """Return the whole payload dict for crown / general assertions."""
        cab = {
            "width_mm": 600, "height_mm": 720, "depth_mm": 350,
            "family": "wall", "door_count": 2, "drawer_count": 0,
            "finished_sides": "none",
            "door_style": "slab", "handle": "none",
            "crown_molding": "none",
        }
        cab.update(cab_overrides)
        cut = {"shelf": None, "shelf_count": 0}
        return self.ConfigSession._cut_list_to_3d_payload(cab, cut)

    def test_finished_sides_none_both_carcass(self):
        sides = self._build_payload("none")
        self.assertEqual(sides["side_L"]["material"], "carcass")
        self.assertEqual(sides["side_R"]["material"], "carcass")

    def test_finished_sides_left_only_L_is_door(self):
        sides = self._build_payload("left")
        self.assertEqual(sides["side_L"]["material"], "door")
        self.assertEqual(sides["side_R"]["material"], "carcass")

    def test_finished_sides_right_only_R_is_door(self):
        sides = self._build_payload("right")
        self.assertEqual(sides["side_L"]["material"], "carcass")
        self.assertEqual(sides["side_R"]["material"], "door")

    def test_finished_sides_both_door(self):
        sides = self._build_payload("both")
        self.assertEqual(sides["side_L"]["material"], "door")
        self.assertEqual(sides["side_R"]["material"], "door")

    # ---------- Crown molding ----------

    def test_crown_none_emits_no_panel(self):
        payload = self._build_full_payload(family="wall", crown_molding="none")
        crowns = [p for p in payload["panels"] if p["name"] == "crown_molding"]
        self.assertEqual(len(crowns), 0)

    def test_crown_simple_on_wall(self):
        payload = self._build_full_payload(family="wall", crown_molding="simple")
        crowns = [p for p in payload["panels"] if p["name"] == "crown_molding"]
        self.assertEqual(len(crowns), 1)
        self.assertEqual(crowns[0]["dims"]["height"], 38)  # 1.5 in cove

    def test_crown_ogee_on_tall(self):
        payload = self._build_full_payload(family="tall", crown_molding="ogee")
        crowns = [p for p in payload["panels"] if p["name"] == "crown_molding"]
        self.assertEqual(len(crowns), 1)
        self.assertEqual(crowns[0]["dims"]["height"], 76)  # 3 in

    def test_crown_skipped_on_base_family(self):
        # Crown molding never applies to base cabinets (they're under
        # a worktop, not the topmost element). Emission gated.
        payload = self._build_full_payload(family="base", crown_molding="ogee")
        crowns = [p for p in payload["panels"] if p["name"] == "crown_molding"]
        self.assertEqual(len(crowns), 0)

    def test_crown_uses_door_material(self):
        payload = self._build_full_payload(family="wall", crown_molding="simple")
        crowns = [p for p in payload["panels"] if p["name"] == "crown_molding"]
        self.assertEqual(crowns[0]["material"], "door")

    def test_two_door_with_handles(self):
        panels = self._emit_doors_panels(
            door_style="slab", handle="knob", door_count=2,
        )
        # 2 slab face panels + 2 knob handles = 4
        self.assertEqual(len(panels), 4)
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 2)
