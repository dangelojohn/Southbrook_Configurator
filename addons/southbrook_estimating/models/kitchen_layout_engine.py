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
           zone_layout=None, worktop_cursor=None, worktop_y=None,
           wall_start_offsets=None):
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
    if wall_start_offsets is None:
        wall_start_offsets = {}

    runs = _resolve_runs(cabinets)

    # Accumulate along-wall cursors per (wall, cursor_name) and place. A
    # wall's run may start past a reserved footprint (a corner cabinet on
    # the adjoining wall) via wall_start_offsets[wall].
    cursors = {}
    placed_by_id = {}
    for wall, run in runs.items():
        for cab in run:
            run_key = _cabinet_run_key(cab, zone_layout, worktop_cursor)
            along = cursors.get(run_key, wall_start_offsets.get(wall, 0))
            y_floor, cross_offset = _cabinet_zone_offsets(
                cab, zone_layout, worktop_y)
            pose = _place_on_wall(
                wall, along, cab, y_floor, cross_offset, room)
            pose["id"] = cab.get("id")
            placed_by_id[id(cab)] = pose
            cursors[run_key] = along + cab.get("width_mm", 0)

    # Emit in original input order for stable, caller-friendly output.
    return [placed_by_id[id(cab)] for cab in cabinets]


# ── Corner resolution (P2) ──────────────────────────────────────────────
# An inside 90° corner exists wherever two adjacent walls BOTH carry a run
# in the same layer (base vs wall). Base and wall corners resolve
# independently. The four room corners and the wall pair that forms each:
_CORNER_SPECS = (
    # name,          (wall_a, wall_b),  (x_key, z_key)
    ("back-left",   ("back",  "left"),  ("0", "0")),
    ("back-right",  ("back",  "right"), ("W", "0")),
    ("front-left",  ("front", "left"),  ("0", "D")),
    ("front-right", ("front", "right"), ("W", "D")),
)


def _layer_of(cab):
    """Which corner layer a cabinet belongs to. Wall (upper) cabinets
    corner independently of base/floor cabinets."""
    if cab.get("cabinet_type") == "wall" or cab.get("family") == "wall":
        return "wall"
    return "base"


def detect_corners(cabinets, room):
    """Find every inside 90° corner that needs a corner cabinet.

    Pure + deterministic. A corner is "active" for a layer when BOTH of
    its two walls carry at least one cabinet in that layer. Detection only
    — resolution (footprint reservation, standard-cabinet removal, corner
    SKU selection, run re-flow, manufacturing write-back) is layered on top
    in the Odoo integration, which owns product identity.

    Returns a list (stable order) of:
      {"corner": "back-left"|..., "layer": "base"|"wall",
       "walls": [wall_a, wall_b],
       "position_mm": {"x": float, "z": float}}
    """
    room_w = room.get("width_mm", 0)
    room_d = room.get("depth_mm", 0)
    coord = {"0": 0.0, "W": float(room_w), "D": float(room_d)}

    walls_with = {"base": set(), "wall": set()}
    for cab in cabinets:
        walls_with[_layer_of(cab)].add(cab.get("wall") or "back")

    out = []
    for name, (wa, wb), (xk, zk) in _CORNER_SPECS:
        for layer in ("base", "wall"):
            if wa in walls_with[layer] and wb in walls_with[layer]:
                out.append({
                    "corner": name,
                    "layer": layer,
                    "walls": [wa, wb],
                    "position_mm": {"x": coord[xk], "z": coord[zk]},
                })
    return out


# ── Auto-distribution (P1) ──────────────────────────────────────────────
# Wrap a flat cabinet list across walls so an L/U kitchen falls out of a
# straight list without any UI. This is ONE layout strategy (the graph /
# drag editor will supply explicit wall assignments later); it only
# produces the semantic (wall, run_seq) inputs the engine already consumes.

def _wall_lengths(room):
    w = room.get("width_mm", 0)
    d = room.get("depth_mm", 0)
    return {"back": w, "front": w, "left": d, "right": d}


def auto_assign_walls(cabinets, room, wall_order=("back", "left")):
    """Assign each cabinet a wall + run_seq by filling walls in wall_order,
    wrapping to the next wall when the current one is full. Base and wall
    (upper) layers distribute independently over the same wall order, so
    uppers land on the same walls as their bases. Pure; returns COPIES with
    'wall'/'run_seq' set (inputs untouched)."""
    wall_len = _wall_lengths(room)
    result = [dict(c) for c in cabinets]
    for layer in ("base", "wall"):
        wi = 0
        used = 0.0
        seq = 0
        for cab in [c for c in result if _layer_of(c) == layer]:
            w = cab.get("width_mm", 0)
            # Wrap when this cabinet would overflow the current wall — but
            # always keep at least one cabinet per wall (used > 0), and
            # never past the last wall (the last wall takes the remainder).
            while (wi < len(wall_order) - 1 and used > 0
                   and used + w > wall_len[wall_order[wi]]):
                wi += 1
                used = 0.0
                seq = 0
            cab["wall"] = wall_order[wi]
            cab["run_seq"] = seq
            used += w
            seq += 1
    return result


# Corner-cabinet footprint (square) + per-layer height, millimetres.
_CORNER_FOOTPRINT_MM = 914.0            # 36"
_CORNER_HEIGHT_MM = {"base": 876.0, "wall": 762.0}   # 34.5" / 30"


def resolve_and_layout(cabinets, room, corner_size_mm=_CORNER_FOOTPRINT_MM,
                       wall_order=("back", "left"), **layout_kwargs):
    """Full auto pipeline: distribute a flat cabinet list across walls,
    detect inside corners, insert a corner-cabinet node at each resolved
    corner (reserving its footprint so nothing overlaps), and lay everything
    out. Pure + deterministic. The engine does NOT assign product SKUs — it
    tags the inserted node `corner_cabinet=True` + corner/layer/handed and
    the Odoo layer maps that to SB-CORNER* / SB-WALL-CORNER.

    v1 resolves the back-left corner (what wall_order=('back','left')
    produces for an L). Other corners are detected + returned but not yet
    footprint-reserved — that lands with the U-shape increment.

    Returns {"cabinets", "placements", "corners", "inserted"}.
    """
    assigned = auto_assign_walls(cabinets, room, wall_order)
    corners = detect_corners(assigned, room)
    inserted = []
    removed_ids = set()
    offsets = {}

    def _run_first(cabs, wall, layer):
        run = [c for c in cabs if (c.get("wall") or "back") == wall
               and _layer_of(c) == layer and not c.get("corner_cabinet")]
        return min(run, key=lambda c: c.get("run_seq", 0), default=None)

    for corner in corners:
        if corner["corner"] != "back-left":
            continue   # v1: only back-left is footprint-reserved
        layer = corner["layer"]
        # The corner cabinet REPLACES the two standard cabinets that meet at
        # the corner (the low-end cabinet of each run) — otherwise they'd
        # overlap the corner cell and the wall would overflow.
        back_first = _run_first(assigned, "back", layer)
        left_first = _run_first(assigned, "left", layer)
        for c in (back_first, left_first):
            if c is not None:
                removed_ids.add(c["id"])
        inserted.append({
            "id": "corner-%s-%s" % (corner["corner"], layer),
            "corner_cabinet": True,
            "corner": corner["corner"],
            "handed": "L",
            "layer": layer,
            "cabinet_type": "wall" if layer == "wall" else "base",
            "family": "wall" if layer == "wall" else "base",
            "width_mm": corner_size_mm,
            "depth_mm": corner_size_mm,
            "height_mm": _CORNER_HEIGHT_MM[layer],
            "zone": "wall" if layer == "wall" else "base_run",
            # Joins the BACK run at its low (x=0) end so it sits in the
            # corner; run_seq -1 makes it first.
            "wall": "back",
            "run_seq": -1,
            "replaced_ids": [c["id"] for c in (back_first, left_first)
                             if c is not None],
        })
        # The LEFT run must start past the corner footprint.
        offsets["left"] = max(offsets.get("left", 0), corner_size_mm)

    final = [dict(c) for c in assigned if c["id"] not in removed_ids]
    final.extend(dict(n) for n in inserted)
    placements = layout(final, room, wall_start_offsets=offsets,
                        **layout_kwargs)
    return {"cabinets": final, "placements": placements, "corners": corners,
            "inserted": inserted, "removed_ids": sorted(removed_ids)}
