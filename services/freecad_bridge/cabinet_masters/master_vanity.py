# SPDX-License-Identifier: LGPL-3.0-only
"""Vanity master.

Base-style carcass with a 200×120 mm rectangular cutout in the back panel
for plumbing supply + waste pass-through.

Defaults: 750 wide × 850 high × 500 deep, 2 doors.
"""
from __future__ import annotations

import sys

from _common import (
    BOX_TH, BACK_TH, RABBET,
    App, Part,
    cuts_for, make_door, make_panel, parse_spec, save_fcstd,
)

DEFAULTS = {
    "width_mm": 750,
    "height_mm": 850,
    "depth_mm": 500,
    "door_count": 2,
    "output_path": "/srv/output/masters/vanity_default.FCStd",
}

# Plumbing cutout.
PLUMB_W = 200.0
PLUMB_H = 120.0


def build(spec: dict) -> str:
    w = float(spec.get("width_mm", DEFAULTS["width_mm"]))
    h = float(spec.get("height_mm", DEFAULTS["height_mm"]))
    d = float(spec.get("depth_mm", DEFAULTS["depth_mm"]))
    doors = int(spec.get("door_count", DEFAULTS["door_count"]))
    out = spec.get("output_path", DEFAULTS["output_path"])

    cuts = cuts_for("vanity", w, h, d, doors)

    doc = App.newDocument("VanityCabinet")

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

    # Back panel — built then cut.
    back_len, back_wid, back_th = cuts["back"]
    back_panel = doc.addObject("Part::Box", "Back_solid")
    back_panel.Length = back_len
    back_panel.Width = back_th
    back_panel.Height = back_wid
    back_panel.Placement.Base = App.Vector(
        BOX_TH - RABBET, d - BACK_TH, BOX_TH - RABBET,
    )

    # Plumbing cutout — centred horizontally, biased low.
    cutout = doc.addObject("Part::Box", "Plumbing_Cutout")
    cutout.Length = PLUMB_W
    cutout.Width = back_th + 4  # cut through with overlap
    cutout.Height = PLUMB_H
    cutout.Placement.Base = App.Vector(
        BOX_TH + back_len / 2 - PLUMB_W / 2 - RABBET,
        d - BACK_TH - 2,
        BOX_TH + 80.0,  # 80mm above the bottom
    )

    # Boolean cut to produce the holed back.
    holed = doc.addObject("Part::Cut", "Back")
    holed.Base = back_panel
    holed.Tool = cutout

    if cuts["adjustable_shelf"]:
        sh_len, sh_wid, sh_th = cuts["adjustable_shelf"]
        make_panel(doc, "Shelf_Adjustable", sh_len, sh_wid, sh_th,
                   x=BOX_TH, y=0.0, z=h / 2)

    opening_w = w - 2 * BOX_TH
    opening_h = h - 2 * BOX_TH
    if doors == 1:
        make_door(doc, "Door", opening_w, opening_h,
                  x_offset=BOX_TH, z_offset=BOX_TH)
    else:
        slab_w = opening_w / doors
        for i in range(doors):
            make_door(doc, f"Door_{i+1}", slab_w, opening_h,
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
