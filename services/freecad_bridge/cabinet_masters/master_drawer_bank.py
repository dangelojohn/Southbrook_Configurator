# SPDX-License-Identifier: LGPL-3.0-only
"""Drawer-bank master.

Same carcass as base; the front is N evenly-divided drawer fronts
(3 by default) instead of door slabs. Interior runners are placed
between sides at each drawer's vertical position.

Defaults: 600 wide × 720 high × 580 deep, 3 drawers.
"""
from __future__ import annotations

import sys

from _common import (
    BOX_TH, BACK_TH, RABBET, DOOR_TH, DOOR_REVEAL,
    App,
    cuts_for, make_panel, parse_spec, save_fcstd,
)

DEFAULTS = {
    "width_mm": 600,
    "height_mm": 720,
    "depth_mm": 580,
    "drawer_count": 3,
    "output_path": "/srv/output/masters/drawer_bank_default.FCStd",
}

# Runner cross-section (placeholder — real Blum hardware references
# replace this once the AVL has Blum part numbers wired).
RUNNER_TH = 16.0
RUNNER_WID = 50.0


def build(spec: dict) -> str:
    w = float(spec.get("width_mm", DEFAULTS["width_mm"]))
    h = float(spec.get("height_mm", DEFAULTS["height_mm"]))
    d = float(spec.get("depth_mm", DEFAULTS["depth_mm"]))
    drawers = int(spec.get("drawer_count", DEFAULTS["drawer_count"]))
    out = spec.get("output_path", DEFAULTS["output_path"])

    # Use 1 "door" for the cut-list — we override the front with drawers.
    cuts = cuts_for("base", w, h, d, 1)

    doc = App.newDocument("DrawerBank")

    side_len, side_wid, side_th = cuts["side_L"]
    make_panel(doc, "Side_L", side_th, side_wid, side_len,
               x=0.0, y=0.0, z=0.0)
    make_panel(doc, "Side_R", side_th, side_wid, side_len,
               x=w - BOX_TH, y=0.0, z=0.0)

    top_len, top_wid, top_th = cuts["top"]
    make_panel(doc, "Top", top_len, top_wid, top_th,
               x=BOX_TH, y=0.0, z=h - BOX_TH)
    bot_len, bot_wid, bot_th = cuts["bottom"]
    make_panel(doc, "Bottom", bot_len, bot_wid, bot_th,
               x=BOX_TH, y=0.0, z=0.0)

    back_len, back_wid, back_th = cuts["back"]
    make_panel(doc, "Back", back_len, back_th, back_wid,
               x=BOX_TH - RABBET, y=d - BACK_TH, z=BOX_TH - RABBET)

    # Drawer fronts — divide the front opening into `drawers` equal slabs
    # stacked vertically.
    opening_w = w - 2 * BOX_TH
    opening_h = h - 2 * BOX_TH
    slab_h = opening_h / drawers
    front_w = opening_w - 2 * DOOR_REVEAL
    front_h = slab_h - 2 * DOOR_REVEAL
    for i in range(drawers):
        front = doc.addObject("Part::Box", f"Drawer_Front_{i+1}")
        front.Length = front_w
        front.Width = DOOR_TH
        front.Height = front_h
        front.Placement.Base = App.Vector(
            BOX_TH + DOOR_REVEAL,
            -DOOR_TH,
            BOX_TH + i * slab_h + DOOR_REVEAL,
        )

        # Runner on each side at the drawer's vertical midpoint.
        for side_x in (BOX_TH, w - BOX_TH - RUNNER_TH):
            runner = doc.addObject("Part::Box", f"Runner_{i+1}_{int(side_x)}")
            runner.Length = RUNNER_TH
            runner.Width = side_wid - 30.0  # ~30mm shy of the back
            runner.Height = RUNNER_WID
            runner.Placement.Base = App.Vector(
                side_x, 15.0,
                BOX_TH + i * slab_h + slab_h / 2 - RUNNER_WID / 2,
            )

    # Toe-kick.
    # Toe-kick: integrated into the side-panel notch per Peter Tuschak's
    # NF14 spec (shared/southbrook_dims.py:toe_kick docstring). No separate
    # panel cut — the notch is added in a finishing pass that runs on top
    # of this master in the FreeCAD GUI.

    doc.recompute()
    return save_fcstd(doc, out)


# freecadcmd does NOT set __name__ to "__main__"; gate on argv[1] so
# importing this module from generate_all.py doesn't trigger a build,
# while "freecadcmd master_X.py" does.
import os as _os
if len(sys.argv) > 1 and _os.path.basename(sys.argv[1]) == _os.path.basename(__file__):
    spec = parse_spec(sys.argv) if len(sys.argv) > 2 else {}
    written = build(spec)
    print(written)
