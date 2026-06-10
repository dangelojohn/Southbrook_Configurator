# SPDX-License-Identifier: LGPL-3.0-only
"""Cabinet-master shared helpers — FreeCAD-side panel placement.

Importing this module from a freecadcmd script gives you the panel
constants from ``shared.southbrook_dims`` plus a small set of helpers
that produce :class:`Part.Box` solids from the cut-list tuples that
``southbrook_dims.panel_cut_list()`` returns.

Conventions (NF14 frameless, all dimensions in mm)
--------------------------------------------------

* X axis = cabinet width (left ↔ right)
* Y axis = cabinet depth (front ↔ back)
* Z axis = cabinet height (bottom ↔ top)
* Origin = front-left-bottom corner of the carcass envelope.

Every helper returns the FreeCAD object so the caller can append it to
the document, recolour it, or compose it into an assembly.
"""
from __future__ import annotations

import sys
from typing import Any

# freecadcmd reinitialises its Python env; PYTHONPATH from the host is
# NOT inherited. Add /srv/shared explicitly so we can pull the canonical
# dims module.
if "/srv/shared" not in sys.path:
    sys.path.insert(0, "/srv/shared")

from southbrook_dims import (  # noqa: E402  (path mutation above is required)
    BOX_TH, BACK_TH, RABBET, DOOR_TH, DOOR_REVEAL,
    panel_cut_list,
)

import FreeCAD as App  # type: ignore  # noqa: E402
import Part  # type: ignore  # noqa: E402


def make_panel(doc, name: str, length: float, width: float, thickness: float,
               x: float = 0.0, y: float = 0.0, z: float = 0.0):
    """Add a thin rectangular panel (Part.Box) at the given position.

    The cut-list tuple semantics from ``southbrook_dims`` are
    ``(length, width, thickness)`` — length runs along the panel's long
    edge, thickness is the material thickness (BOX_TH for melamine,
    BACK_TH for hardboard, DOOR_TH for door material).

    The caller picks how to orient those three dimensions in 3D space.
    """
    box = doc.addObject("Part::Box", name)
    box.Length = length
    box.Width = width
    box.Height = thickness
    box.Placement.Base = App.Vector(x, y, z)
    return box


def make_door(doc, name: str, opening_width: float, opening_height: float,
              x_offset: float, z_offset: float):
    """Place a door slab in front of the carcass.

    Door size = opening minus the uniform DOOR_REVEAL on all four edges.
    Placed at Y = -DOOR_TH so it sits flush in front of the cabinet front.
    """
    door_w = opening_width - 2 * DOOR_REVEAL
    door_h = opening_height - 2 * DOOR_REVEAL
    door = doc.addObject("Part::Box", name)
    door.Length = door_w
    door.Width = DOOR_TH
    door.Height = door_h
    door.Placement.Base = App.Vector(
        x_offset + DOOR_REVEAL,
        -DOOR_TH,
        z_offset + DOOR_REVEAL,
    )
    return door


def cuts_for(family: str, width_mm: float, height_mm: float, depth_mm: float,
             door_count: int = 1) -> dict[str, Any]:
    """Thin wrapper around ``southbrook_dims.panel_cut_list`` for the
    families the master generators care about. Returns the same dict
    shape ``panel_cut_list`` produces, plus the envelope inputs echoed
    so callers don't have to thread them through.
    """
    cuts = panel_cut_list(
        family=family,
        width_mm=width_mm,
        height_mm=height_mm,
        depth_mm=depth_mm,
        door_count=door_count,
    )
    cuts["_envelope"] = {
        "width_mm": width_mm,
        "height_mm": height_mm,
        "depth_mm": depth_mm,
        "door_count": door_count,
    }
    return cuts


def save_fcstd(doc, output_path: str) -> str:
    """Save the document and return the absolute path written."""
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.saveAs(output_path)
    return output_path


def parse_spec(argv: list[str]) -> dict[str, Any]:
    """Pull the JSON spec out of ``freecadcmd`` argv.

    freecadcmd's argv shape is::

        ['/path/to/freecadcmd', 'master_X.py', '--', '<spec_json>']

    so the spec is always the last item.
    """
    import json
    if not argv:
        raise SystemExit("no spec provided")
    return json.loads(argv[-1])
