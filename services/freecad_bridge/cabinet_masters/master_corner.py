# SPDX-License-Identifier: LGPL-3.0-only
"""Corner cabinet master — L-shaped carcass + bi-fold door.

Two-arm L with the inside corner at the origin. Each arm has its own
side, back, and shared top / bottom hinged at the joint. The door is a
bi-fold pair occupying the front face.

Defaults: 900 wide × 720 high × 580 deep (per arm), 2 doors (bi-fold).
"""
from __future__ import annotations

import sys

from _common import (
    BOX_TH, BACK_TH, RABBET,
    App,
    cuts_for, make_door, make_panel, parse_spec, save_fcstd,
)

DEFAULTS = {
    "width_mm": 900,
    "height_mm": 720,
    "depth_mm": 580,
    "door_count": 2,
    "output_path": "/srv/output/masters/corner_default.FCStd",
}


def build(spec: dict) -> str:
    w = float(spec.get("width_mm", DEFAULTS["width_mm"]))
    h = float(spec.get("height_mm", DEFAULTS["height_mm"]))
    d = float(spec.get("depth_mm", DEFAULTS["depth_mm"]))
    doors = int(spec.get("door_count", DEFAULTS["door_count"]))
    out = spec.get("output_path", DEFAULTS["output_path"])

    cuts = cuts_for("corner", w, h, d, doors)

    doc = App.newDocument("CornerCabinet")

    # Arm A — runs along X axis (front-facing)
    side_len, side_wid, side_th = cuts["side_L"]
    make_panel(doc, "ArmA_Side_Front", side_th, side_wid, side_len,
               x=0.0, y=0.0, z=0.0)
    make_panel(doc, "ArmA_Side_Back", side_th, side_wid, side_len,
               x=w - BOX_TH, y=0.0, z=0.0)

    # Arm B — runs along Y axis (rotated 90° clockwise around the corner).
    # In a real CAD model this is achieved by a placement rotation; for
    # the master we add a parallel set of panels translated to the other
    # leg's footprint.
    make_panel(doc, "ArmB_Side_Inner", side_th, side_wid, side_len,
               x=0.0, y=w - BOX_TH, z=0.0)

    # Shared top + bottom — L-shaped panel approximated by two rectangles.
    top_len, top_wid, top_th = cuts["top"]
    make_panel(doc, "Top_ArmA", top_len, top_wid, top_th,
               x=BOX_TH, y=0.0, z=h - BOX_TH)
    make_panel(doc, "Top_ArmB", top_wid, top_len, top_th,
               x=0.0, y=BOX_TH, z=h - BOX_TH)

    bot_len, bot_wid, bot_th = cuts["bottom"]
    make_panel(doc, "Bottom_ArmA", bot_len, bot_wid, bot_th,
               x=BOX_TH, y=0.0, z=0.0)
    make_panel(doc, "Bottom_ArmB", bot_wid, bot_len, bot_th,
               x=0.0, y=BOX_TH, z=0.0)

    # Backs — one per arm.
    back_len, back_wid, back_th = cuts["back"]
    make_panel(doc, "Back_ArmA", back_len, back_th, back_wid,
               x=BOX_TH - RABBET, y=d - BACK_TH, z=BOX_TH - RABBET)
    make_panel(doc, "Back_ArmB", back_th, back_len, back_wid,
               x=d - BACK_TH, y=BOX_TH - RABBET, z=BOX_TH - RABBET)

    # Bi-fold door — two equal slabs across the front face of Arm A.
    opening_w = w - 2 * BOX_TH
    opening_h = h - 2 * BOX_TH
    slab_w = opening_w / max(doors, 1)
    for i in range(max(doors, 1)):
        make_door(doc, f"BiFold_Door_{i+1}", slab_w, opening_h,
                  x_offset=BOX_TH + i * slab_w, z_offset=BOX_TH)

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
