# SPDX-License-Identifier: LGPL-3.0-only
"""Base cabinet master (NF14 frameless).

Assembly: two sides, top, bottom, back (rabbeted), 1 adjustable shelf,
1 or 2 door slabs, toe-kick.

Defaults: 600 wide × 720 high × 580 deep, 1 door.

Invocation::

    freecadcmd master_base.py -- '{"width_mm":600,"height_mm":720,
        "depth_mm":580,"door_count":1,
        "output_path":"/srv/output/masters/base_default.FCStd"}'
"""
from __future__ import annotations

import sys

from _common import (  # noqa: E402  (sibling import)
    BOX_TH, BACK_TH, RABBET, DOOR_TH,
    App, Part,
    cuts_for, make_door, make_panel, parse_spec, save_fcstd,
)

DEFAULTS = {
    "width_mm": 600,
    "height_mm": 720,
    "depth_mm": 580,
    "door_count": 1,
    "output_path": "/srv/output/masters/base_default.FCStd",
}


def build(spec: dict) -> str:
    w = float(spec.get("width_mm", DEFAULTS["width_mm"]))
    h = float(spec.get("height_mm", DEFAULTS["height_mm"]))
    d = float(spec.get("depth_mm", DEFAULTS["depth_mm"]))
    doors = int(spec.get("door_count", DEFAULTS["door_count"]))
    out = spec.get("output_path", DEFAULTS["output_path"])

    cuts = cuts_for("base", w, h, d, doors)

    doc = App.newDocument("BaseCabinet")

    # Sides — vertical panels at x=0 and x=w-BOX_TH, full height.
    side_len, side_wid, side_th = cuts["side_L"]
    make_panel(doc, "Side_L", side_th, side_wid, side_len,
               x=0.0, y=0.0, z=0.0)
    make_panel(doc, "Side_R", side_th, side_wid, side_len,
               x=w - BOX_TH, y=0.0, z=0.0)

    # Top + bottom — horizontal panels spanning between sides.
    top_len, top_wid, top_th = cuts["top"]
    make_panel(doc, "Top", top_len, top_wid, top_th,
               x=BOX_TH, y=0.0, z=h - BOX_TH)
    bot_len, bot_wid, bot_th = cuts["bottom"]
    make_panel(doc, "Bottom", bot_len, bot_wid, bot_th,
               x=BOX_TH, y=0.0, z=0.0)

    # Back — flush at y = d - BACK_TH, captured in the rabbet.
    back_len, back_wid, back_th = cuts["back"]
    make_panel(doc, "Back", back_len, back_th, back_wid,
               x=BOX_TH - RABBET, y=d - BACK_TH, z=BOX_TH - RABBET)

    # Adjustable shelf — at mid height (the GUI user can move it).
    if cuts["adjustable_shelf"]:
        sh_len, sh_wid, sh_th = cuts["adjustable_shelf"]
        make_panel(doc, "Shelf_Adjustable", sh_len, sh_wid, sh_th,
                   x=BOX_TH, y=0.0, z=h / 2)

    # Doors — split the front opening across `doors` slabs.
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
