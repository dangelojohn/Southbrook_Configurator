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
                           door_count=1, W=600, H=720):
        panels = []
        self.ConfigSession._emit_doors(
            panels=panels, W=W, H=H, y0=0, DOOR_TH=18, DOOR_REVEAL=3,
            door_count=door_count,
            door_style=door_style, handle=handle,
        )
        return panels

    def _emit_drawer_panels(self, door_style="slab", handle="none",
                            drawer_count=3, W=600, H=720):
        panels = []
        self.ConfigSession._emit_drawer_fronts(
            panels=panels, W=W, H=H, y0=0, DOOR_TH=18, DOOR_REVEAL=3,
            drawer_count=drawer_count,
            door_style=door_style, handle=handle,
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

    def test_bar_pull_emits_one_hardware_panel(self):
        panels = self._emit_doors_panels(door_style="slab", handle="bar_pull")
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 1)

    def test_knob_emits_one_hardware_panel(self):
        panels = self._emit_doors_panels(door_style="slab", handle="knob")
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 1)
        # Knob is roughly cubic
        d = hardware[0]["dims"]
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

    def test_two_door_with_handles(self):
        panels = self._emit_doors_panels(
            door_style="slab", handle="knob", door_count=2,
        )
        # 2 slab face panels + 2 knob handles = 4
        self.assertEqual(len(panels), 4)
        hardware = [p for p in panels if p.get("material") == "hardware"]
        self.assertEqual(len(hardware), 2)
