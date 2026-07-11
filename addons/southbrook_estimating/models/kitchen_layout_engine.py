# SPDX-License-Identifier: LGPL-3.0-only
"""Southbrook Kitchen — pure layout engine.

The single source of truth for *where and how* cabinets sit in a room.

Design contract (P0, 2026-07-11):
  * PURE. No Odoo imports, no ORM, no `self`, no I/O, no globals. Every
    input arrives as plain data; every output is plain data. This module
    must be importable and runnable with a bare `python3`.
  * DETERMINISTIC + STATELESS. Same inputs → same outputs, always. No
    randomness, no clocks, no mutation of the inputs.
  * UI-INDEPENDENT. The engine never knows whether its caller is the
    read-only Preview, the drag editor, an auto-layout pass, an import
    wizard, or a future AI designer. It consumes *semantic* placement
    inputs and emits manufacturable placements.

Domain separation (John, 2026-07-11):
  * Manufacturing domain (`sale.order.line`) = product/qty/price/BOM. NOT
    an input concept here beyond product identity + dimensions.
  * Layout domain (`kitchen.design.line`) = wall, run_seq, offsets,
    rotation, adjacency. THIS is the engine's input.

Evolution path — Cabinet Relationship Graph:
  Today runs are derived from (wall, run_seq). That is deliberately isolated
  in `_resolve_runs()`. Tomorrow, runs come from an adjacency graph
  (connects_to / terminates_into / corner_with / filler_before / ...), and
  walls become just one constraint type. Only `_resolve_runs()` changes;
  the placement mechanics below are graph-agnostic.

Coordinate frame (millimetres, right-handed, matches the existing scene):
  * +X runs along the back wall, left→right.
  * +Z runs from the back wall (z=0) toward the front of the room (z=depth).
  * +Y is up. rotation_deg is a right-handed rotation about +Y.
  * A cabinet's local pose faces the room (out of the back wall) at
    rotation_deg = 0.
"""

# Wall geometry table. Each wall declares:
#   along : which world axis the run advances on ("x" or "z")
#   rot   : the cabinet's Y-rotation (deg) when placed on this wall
# The cross-axis anchor (which wall the run hugs) is computed from the room
# and the zone's cross-offset in `_place_on_wall()`.
WALLS = ("back", "front", "left", "right")

_WALL_SPEC = {
    "back":  {"along": "x", "rot": 0},
    "front": {"along": "x", "rot": 180},
    "left":  {"along": "z", "rot": 90},
    "right": {"along": "z", "rot": 270},
}

# Fallback zone layout — the ORM caller MUST pass the model's authoritative
# `sale.order._ZONE_LAYOUT` so there is exactly one source of truth. This
# copy exists only so the pure module is self-contained for offline tests.
_DEFAULT_ZONE_LAYOUT = {
    "base_run":  ("ground", 0,    0),
    "wall":      ("wall",   1400, 0),
    "tall":      ("ground", 0,    0),
    "island":    ("island", 0,    -2500),
    "accessory": ("ground", 0,    0),
    "other":     ("other",  0,    -3000),
}
_DEFAULT_WORKTOP_CURSOR = "ground"
_DEFAULT_WORKTOP_Y = 762


def _cabinet_run_key(cab, zone_layout, worktop_cursor):
    """The accumulator bucket a cabinet advances.

    A run is identified by (wall, cursor_name): cabinets on the same wall
    that share a zone-cursor advance the same running offset. Back-wall
    base/tall/accessory all share the "ground" cursor exactly as the legacy
    single-run engine did — so an all-back kitchen is byte-identical.
    """
    if cab.get("family") == "worktop":
        cursor_name = worktop_cursor
    else:
        zone = cab.get("zone") or "base_run"
        cursor_name = zone_layout.get(zone, ("ground", 0, 0))[0]
    return (cab.get("wall") or "back", cursor_name)


def _cabinet_zone_offsets(cab, zone_layout, worktop_y):
    """(y_floor_mm, cross_offset_mm) for a cabinet, by family/zone."""
    if cab.get("family") == "worktop":
        return worktop_y, 0
    zone = cab.get("zone") or "base_run"
    _cursor, y_floor, z_offset = zone_layout.get(zone, ("ground", 0, 0))
    return y_floor, z_offset


def _resolve_runs(cabinets):
    """Group cabinets into ordered runs.

    P0: one run per wall, ordered by (run_seq, input index). This is the
    ONLY place wall-vs-graph organisation lives — the future relationship
    graph replaces this function and nothing else.

    Returns a dict {wall: [cab, cab, ...]} with each list run-ordered.
    """
    runs = {}
    for idx, cab in enumerate(cabinets):
        wall = cab.get("wall") or "back"
        runs.setdefault(wall, []).append((idx, cab))
    for wall in runs:
        runs[wall].sort(key=lambda pair: (pair[1].get("run_seq", 0), pair[0]))
        runs[wall] = [cab for _idx, cab in runs[wall]]
    return runs


def _place_on_wall(wall, along_cursor, cab, y_floor, cross_offset, room):
    """Compute one cabinet's (x, y, z, rotation_deg) on a given wall.

    `along_cursor` is the running offset (mm) already consumed on this wall's
    run before this cabinet; the cabinet's centre sits at along_cursor + w/2.
    `cross_offset` is the zone's cross-axis offset (island/other tuck-away on
    back/front; wall-inset on left/right).
    """
    w = cab.get("width_mm", 0)
    spec = _WALL_SPEC[wall]
    centre = along_cursor + w / 2.0
    room_w = room.get("width_mm", 0)
    room_d = room.get("depth_mm", 0)

    if wall == "back":
        return {"x": centre,               "y": y_floor, "z": cross_offset,
                "rotation_deg": spec["rot"]}
    if wall == "front":
        return {"x": centre,               "y": y_floor, "z": room_d - cross_offset,
                "rotation_deg": spec["rot"]}
    if wall == "left":
        return {"x": cross_offset,         "y": y_floor, "z": centre,
                "rotation_deg": spec["rot"]}
    # right
    return {"x": room_w - cross_offset,    "y": y_floor, "z": centre,
            "rotation_deg": spec["rot"]}


def layout(cabinets, room,
           zone_layout=None, worktop_cursor=None, worktop_y=None):
    """Resolve semantic placement inputs into manufacturable placements.

    Args:
      cabinets: list of dicts. Each: {
          "id": hashable, "width_mm", "height_mm", "depth_mm",
          "family": str, "zone": str (optional),
          "wall": one of WALLS (default "back"),
          "run_seq": int (optional, default 0),
      }
      room: {"width_mm", "depth_mm", "height_mm"}.
      zone_layout / worktop_cursor / worktop_y: the model's authoritative
          constants. Defaults mirror sale.order for offline tests.

    Returns: list of placement dicts, ONE per input cabinet, in the SAME
      order as `cabinets`: {"id", "x", "y", "z", "rotation_deg"} (mm/deg).
      Inputs are never mutated.
    """
    if zone_layout is None:
        zone_layout = _DEFAULT_ZONE_LAYOUT
    if worktop_cursor is None:
        worktop_cursor = _DEFAULT_WORKTOP_CURSOR
    if worktop_y is None:
        worktop_y = _DEFAULT_WORKTOP_Y

    runs = _resolve_runs(cabinets)

    # Accumulate along-wall cursors per (wall, cursor_name) and place.
    cursors = {}
    placed_by_id = {}
    for wall, run in runs.items():
        for cab in run:
            run_key = _cabinet_run_key(cab, zone_layout, worktop_cursor)
            along = cursors.get(run_key, 0)
            y_floor, cross_offset = _cabinet_zone_offsets(
                cab, zone_layout, worktop_y)
            pose = _place_on_wall(
                wall, along, cab, y_floor, cross_offset, room)
            pose["id"] = cab.get("id")
            placed_by_id[id(cab)] = pose
            cursors[run_key] = along + cab.get("width_mm", 0)

    # Emit in original input order for stable, caller-friendly output.
    return [placed_by_id[id(cab)] for cab in cabinets]
