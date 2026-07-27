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

ALLOWED_ROTATIONS = (0, 90, 180, 270)


class LayoutCapacityExceeded(Exception):
    """Raised when cabinets cannot physically fit the available walls.

    Impossible layouts fail explicitly here rather than silently overflowing
    the room (which would ship a non-manufacturable design). Carries the
    numbers so a caller can surface e.g. ROOM_TOO_SMALL(capacity, requested).

    NOTE: the raise fires on the geometric postcondition (a cabinet's
    footprint falls outside the room), NOT on the capacity precheck — so
    requested_mm is not necessarily greater than capacity_mm (a corner
    reservation can push an otherwise-fitting run past the wall even when
    total requested run length is under capacity). The message must not
    claim ">" for that reason.

    `outside`, when given, is a list of dicts describing each cabinet that
    failed the in-room postcondition: {"id", "overflow_mm", "wall"} — the
    worst-case overhang (mm) past the room bounds and the wall it was on.
    """
    def __init__(self, capacity_mm, requested_mm, detail="", outside=None):
        self.capacity_mm = capacity_mm
        self.requested_mm = requested_mm
        self.detail = detail
        self.outside = outside or []
        super().__init__(
            "layout does not fit: %d cabinet(s) outside room "
            "(capacity %.0fmm, requested %.0fmm)%s" % (
                len(self.outside), capacity_mm, requested_mm,
                (" — %s" % detail) if detail else ""))


# ── Geometry helpers (shared by the engine + the invariant suite) ───────
# Footprint math matches the engine's placement convention exactly: the
# along-wall axis is CENTRED on the placement coord; the depth extends from
# the wall face into the room, in the direction set by rotation_deg.

def footprint_mm(cab, place):
    """World-space AABB (x0, x1, z0, z1) of a placed cabinet."""
    w = cab.get("width_mm", 0)
    d = cab.get("depth_mm", 0)
    x = place["x"]
    z = place["z"]
    rot = int(round(place.get("rotation_deg", 0))) % 360
    if rot == 0:        # back: along +X, depth +Z
        return (x - w / 2, x + w / 2, z, z + d)
    if rot == 180:      # front: along +X, depth -Z
        return (x - w / 2, x + w / 2, z - d, z)
    if rot == 90:       # left: along +Z, depth +X
        return (x, x + d, z - w / 2, z + w / 2)
    # rot == 270        # right: along +Z, depth -X
    return (x - d, x, z - w / 2, z + w / 2)


def anchor_pose_mm(cab, place):
    """Convert an engine placement (along-axis CENTRED — the module's
    internal convention, see footprint_mm) to the persisted anchor
    convention (COORDINATE_CONTRACT.md: back-left-bottom corner, mesh
    rotated about +Y around the anchor). Returns a NEW dict; inputs
    untouched. y and rotation_deg pass through unchanged."""
    w = cab.get("width_mm", 0)
    x = place["x"]
    z = place["z"]
    rot = int(round(place.get("rotation_deg", 0))) % 360
    out = dict(place)
    if rot == 0:
        out["x"] = x - w / 2.0
    elif rot == 90:
        out["z"] = z + w / 2.0
    elif rot == 180:
        out["x"] = x + w / 2.0
    else:   # 270
        out["z"] = z - w / 2.0
    return out


def footprint_from_anchor_mm(cab, place):
    """World AABB (x0,x1,z0,z1) of a cabinet whose place uses the
    persisted ANCHOR convention (back-left-bottom corner + rotation
    about the anchor) — the renderer's math, for validating persisted
    poses. Sibling of footprint_mm (which assumes the engine's
    along-axis-centred convention)."""
    w = cab.get("width_mm", 0)
    d = cab.get("depth_mm", 0)
    x = place["x"]
    z = place["z"]
    rot = int(round(place.get("rotation_deg", 0))) % 360
    if rot == 0:
        return (x, x + w, z, z + d)
    if rot == 180:
        return (x - w, x, z - d, z)
    if rot == 90:
        return (x, x + d, z - w, z)
    # rot == 270
    return (x - d, x, z, z + w)


def footprints_overlap(a, b, eps=1.0):
    return (a[0] < b[1] - eps and b[0] < a[1] - eps and
            a[2] < b[3] - eps and b[2] < a[3] - eps)


def within_room(cab, place, room, eps=2.0):
    W = room.get("width_mm", 0)
    D = room.get("depth_mm", 0)
    x0, x1, z0, z1 = footprint_mm(cab, place)
    return (x0 >= -eps and x1 <= W + eps and z0 >= -eps and z1 <= D + eps)


def wall_capacity_mm(room, wall_order):
    """Total along-wall run length available across the walls in wall_order."""
    lengths = _wall_lengths(room)
    return sum(lengths.get(w, 0) for w in wall_order)


def check_capacity(cabinets, room, wall_order=("back", "left")):
    """Pre-flight capacity check (no raising). Returns
    {ok, capacity_mm, requested_mm} where requested is the widest single
    layer's total run length (base and wall layers each run the walls)."""
    cap = wall_capacity_mm(room, wall_order)
    per_layer = {"base": 0.0, "wall": 0.0}
    for c in cabinets:
        per_layer[_layer_of(c)] += c.get("width_mm", 0)
    requested = max(per_layer.values()) if per_layer else 0.0
    return {"ok": requested <= cap, "capacity_mm": cap,
            "requested_mm": requested}

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

    # A cabinet may carry an explicit `__pose` (x/y/z/rotation_deg) — used for
    # "standalone" corner cabinets that don't belong to any run (a both-high
    # corner like front-right, where neither wall's low end is at the corner
    # so it can't be positioned by joining a run). Placed verbatim; consumes
    # no cursor.
    runs = _resolve_runs([c for c in cabinets if not c.get("__pose")])

    # Accumulate along-wall cursors per (wall, cursor_name) and place. A
    # wall's run may start past a reserved footprint (a corner cabinet on
    # the adjoining wall) via wall_start_offsets[wall].
    cursors = {}
    placed_by_id = {}
    for cab in cabinets:
        if cab.get("__pose"):
            pose = dict(cab["__pose"])
            pose["id"] = cab.get("id")
            placed_by_id[id(cab)] = pose
    for wall, run in runs.items():
        for cab in run:
            run_key = _cabinet_run_key(cab, zone_layout, worktop_cursor)
            # wall_start_offsets is keyed by (wall, layer) — a corner
            # resolved for ONE layer (base or wall) on a wall must not
            # shove the OTHER layer's run on that same wall (I1: a
            # base-only corner shouldn't shift the wall/upper run).
            along = cursors.get(
                run_key, wall_start_offsets.get((wall, _layer_of(cab)), 0))
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


# Corner-cabinet footprint (square) + per-layer height, millimetres. Defined
# here (ahead of detect_corners) so it can serve as that function's default
# `corner_size_mm`; resolve_and_layout below re-exports/reuses the same
# constant.
_CORNER_FOOTPRINT_MM = 914.0            # 36"
_CORNER_HEIGHT_MM = {"base": 876.0, "wall": 762.0}   # 34.5" / 30"


def _corner_cell_aabb(xk, zk, room, corner_size_mm):
    """World-space AABB of a corner's `corner_size_mm` square cell, anchored
    at the room corner named by (xk, zk) and extending toward the room
    interior."""
    room_w = room.get("width_mm", 0)
    room_d = room.get("depth_mm", 0)
    if xk == "0":
        x0, x1 = 0.0, corner_size_mm
    else:   # "W"
        x0, x1 = room_w - corner_size_mm, room_w
    if zk == "0":
        z0, z1 = 0.0, corner_size_mm
    else:   # "D"
        z0, z1 = room_d - corner_size_mm, room_d
    return (x0, x1, z0, z1)


def detect_corners(cabinets, room, placements=None,
                    corner_size_mm=_CORNER_FOOTPRINT_MM):
    """Find every inside 90° corner that needs a corner cabinet.

    Pure + deterministic. Detection only — resolution (footprint
    reservation, standard-cabinet removal, corner SKU selection, run
    re-flow, manufacturing write-back) is layered on top in the Odoo
    integration, which owns product identity.

    When `placements` is given (the placed x/y/z/rotation_deg for each
    cabinet, as returned by `layout()`), a corner is "active" for a layer
    only when BOTH of its two walls have a cabinet in that layer whose
    PLACED footprint actually overlaps the corner's `corner_size_mm` cell
    (geometric occupancy) — merely having *some* cabinet on each wall is
    not enough; it must reach the corner. When `placements` is None (legacy
    callers), falls back to the old wall-occupancy test.

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

    placed_by_id = {p["id"]: p for p in placements} if placements is not None else None

    def _wall_reaches_cell(wall, layer, cell):
        for cab in cabinets:
            if (cab.get("wall") or "back") != wall or _layer_of(cab) != layer:
                continue
            place = placed_by_id.get(cab.get("id"))
            if place is None:
                continue
            if footprints_overlap(footprint_mm(cab, place), cell):
                return True
        return False

    out = []
    for name, (wa, wb), (xk, zk) in _CORNER_SPECS:
        cell = (_corner_cell_aabb(xk, zk, room, corner_size_mm)
                if placed_by_id is not None else None)
        for layer in ("base", "wall"):
            if placed_by_id is None:
                active = wa in walls_with[layer] and wb in walls_with[layer]
            else:
                active = (_wall_reaches_cell(wa, layer, cell)
                          and _wall_reaches_cell(wb, layer, cell))
            if active:
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


# Corner resolution geometry, keyed by corner name:
#   (host_wall, other_wall, other_end, handed)
#   host_wall  — the run whose LOW end is at this corner; the corner cabinet
#                joins it at run_seq -1 (consuming its cursor so the run
#                flows past the reserved cell).
#   other_wall — the adjoining run.
#   other_end  — where the adjoining run meets the corner: "first" (its low
#                end → also offset it by cs) or "last" (its high end simply
#                terminates at the cell → no offset).
#   handed     — corner handedness hint for downstream SKU selection.
# Covers every corner that has a LOW-end host (a run whose origin is at the
# corner). front-right has neither wall's low end at it → _CORNER_STANDALONE.
_CORNER_RESOLVE = {
    "back-left":   ("back",  "left",  "first", "L"),
    "back-right":  ("right", "back",  "last",  "R"),
    "front-left":  ("front", "left",  "last",  "R"),
}

# "Both-high" corners: neither wall's LOW end is at the corner, so the corner
# cabinet can't be positioned by joining a run at run_seq -1. It is placed
# STANDALONE (explicit __pose filling the reserved cell), and both adjoining
# runs are capped — any standard cabinet overlapping the cell is removed
# (replaced by the corner). Keyed by name → (x_key, z_key) of the cell's FAR
# corner (the room corner); the cell is the cs-square inset from there.
_CORNER_STANDALONE = {
    "front-right": ("W", "D"),
}

# `(x_key, z_key)` of each _CORNER_RESOLVE corner's OWN cell (not the "far"
# corner used by _CORNER_STANDALONE) — reuses the same keys as _CORNER_SPECS,
# indexed by corner name for the pose math below.
_CORNER_XZ_KEYS = {name: (xk, zk) for name, _walls, (xk, zk) in _CORNER_SPECS}

# How each _CORNER_RESOLVE corner PRESENTS: (wall tag persisted to
# kitchen.design.line, rotation_deg). `host_wall` (in _CORNER_RESOLVE above)
# stays solely the adjoining-run cursor bookkeeping key — it must NOT be
# assumed to be the emitted `wall`/orientation, because for back-left that
# coupling IS the "vanishing cabinet" bug: host_wall="back" has rotation 0
# (_WALL_SPEC["back"]["rot"]), which is visually IDENTICAL to an ordinary
# back-wall cabinet, so the corner rendered flat on the back wall instead of
# turning into the corner.
#   back-left  -> "left" / 90 (left wall's rotation). Re-tagging + rotating
#                 to the LEFT wall's convention makes the corner read as the
#                 turn into the left run — the fix for the reported bug, and
#                 it also happens to be the wall this whole plan is about
#                 keeping visible.
#   back-right -> "right" / 270 (right wall's rotation). host_wall="right"
#                 already gives a non-zero, distinct rotation — unchanged;
#                 this is the regression guard the plan calls out as
#                 "already correct".
#   front-left -> "front" / 180 (front wall's rotation). host_wall="front"
#                 likewise already gives a non-zero, distinct rotation —
#                 unchanged, second regression guard.
_CORNER_RESOLVE_PRESENTATION = {
    "back-left":   ("left",  90),
    "back-right":  ("right", 270),
    "front-left":  ("front", 180),
}


def _corner_node_pose(xk, zk, room, corner_size_mm, rotation_deg, y_floor):
    """Explicit (x, y, z, rotation_deg) pose whose footprint AABB (per
    `footprint_mm`'s own placement convention) is EXACTLY the corner's
    `corner_size_mm` cell, for any of the four `ALLOWED_ROTATIONS`. Used so
    the inserted corner node's `__pose` lands in the corner cell regardless
    of which run's cursor (`host_wall`) it was bookkept against."""
    x0, x1, z0, z1 = _corner_cell_aabb(xk, zk, room, corner_size_mm)
    rot = int(round(rotation_deg)) % 360
    if rot == 0:
        x, z = (x0 + x1) / 2.0, z0
    elif rot == 180:
        x, z = (x0 + x1) / 2.0, z1
    elif rot == 90:
        x, z = x0, (z0 + z1) / 2.0
    else:   # 270
        x, z = x1, (z0 + z1) / 2.0
    return {"x": x, "y": y_floor, "z": z, "rotation_deg": rot}


def resolve_and_layout(cabinets, room, corner_size_mm=_CORNER_FOOTPRINT_MM,
                       wall_order=("back", "left"), auto_assign=True,
                       **layout_kwargs):
    """Full pipeline: (optionally distribute a flat cabinet list across
    walls), detect inside corners, insert a corner-cabinet node at each
    resolved corner (reserving its footprint so nothing overlaps), and lay
    everything out. Pure + deterministic. The engine does NOT assign product
    SKUs — it tags the inserted node `corner_cabinet=True` + corner/layer/
    handed and the Odoo layer maps that to SB-CORNER* / SB-WALL-CORNER.

    auto_assign=True  → wrap a flat list across walls (the button on an
                        unassigned order).
    auto_assign=False → RESPECT the cabinets' existing wall/run_seq (the
                        interactive flow, where the user placed each cabinet
                        on a wall) and just resolve corners in place.

    Resolves ALL FOUR inside corners: back-left, back-right and front-left
    have a low-end host (a run whose origin sits at the corner) so the corner
    cabinet joins that run at run_seq -1; front-right is "both-high" (neither
    wall's low end is there) so it is placed standalone in its cell and both
    adjoining runs are capped. Handles an L, a U, or a full G-shape.

    Returns {"cabinets", "assigned", "placements", "corners", "inserted"}.
    """
    assigned = (auto_assign_walls(cabinets, room, wall_order) if auto_assign
                else [dict(c) for c in cabinets])
    # Detect corners against REAL placed footprints (geometric occupancy),
    # not mere wall occupancy — a provisional layout of the as-assigned
    # cabinets (before any corner insertion/removal) is enough to tell
    # whether each run's cabinets actually reach the shared corner cell.
    provisional_placements = layout(assigned, room, **layout_kwargs)
    corners = detect_corners(assigned, room, placements=provisional_placements,
                              corner_size_mm=corner_size_mm)
    inserted = []
    removed_ids = set()
    offsets = {}
    standalone_cells = []   # [(cell_aabb, corner_node)] for the cap pass
    room_w = room.get("width_mm", 0)
    room_d = room.get("depth_mm", 0)
    zl = layout_kwargs.get("zone_layout") or _DEFAULT_ZONE_LAYOUT

    def _run_end(cabs, wall, layer, end):
        run = [c for c in cabs if (c.get("wall") or "back") == wall
               and _layer_of(c) == layer and not c.get("corner_cabinet")]
        pick = min if end == "first" else max
        return pick(run, key=lambda c: c.get("run_seq", 0), default=None)

    for corner in corners:
        layer = corner["layer"]
        if corner["corner"] in _CORNER_STANDALONE:
            # Both-high corner (front-right): place the corner cabinet
            # STANDALONE filling its cell, and mark the cell for the cap pass.
            cell = (room_w - corner_size_mm, room_w,
                    room_d - corner_size_mm, room_d)
            y_floor = zl.get("wall" if layer == "wall" else "base_run",
                             ("ground", 0, 0))[1]
            node = {
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
                "wall": "right",
                # Explicit pose (rot 0) whose AABB is exactly the cell.
                "__pose": {"x": room_w - corner_size_mm / 2.0, "y": y_floor,
                           "z": room_d - corner_size_mm, "rotation_deg": 0},
                "replaced_ids": [],
            }
            inserted.append(node)
            standalone_cells.append((cell, node))
            continue
        spec = _CORNER_RESOLVE.get(corner["corner"])
        if spec is None:
            continue   # remaining corners not yet footprint-reserved
        host_wall, other_wall, other_end, handed = spec
        # The corner cabinet REPLACES the two standard cabinets that meet at
        # the corner — otherwise they'd overlap the corner cell / overflow.
        # `host_wall` identifies the run whose LOW end is at this corner —
        # used ONLY to find which two standard cabinets to remove and to
        # reserve that run's cursor space (via `offsets[host_wall]` below).
        # It is deliberately NOT used to derive the emitted `wall`/rotation
        # (see `_CORNER_RESOLVE_PRESENTATION`) — the corner gets an explicit
        # `__pose` centred in ITS OWN corner cell, so it renders in the
        # corner regardless of which run's cursor it was bookkept against.
        host_first = _run_end(assigned, host_wall, layer, "first")
        other_cab = _run_end(assigned, other_wall, layer, other_end)
        for c in (host_first, other_cab):
            if c is not None:
                removed_ids.add(c["id"])
        wall_tag, rotation_deg = _CORNER_RESOLVE_PRESENTATION[corner["corner"]]
        xk, zk = _CORNER_XZ_KEYS[corner["corner"]]
        y_floor = zl.get("wall" if layer == "wall" else "base_run",
                         ("ground", 0, 0))[1]
        pose = _corner_node_pose(xk, zk, room, corner_size_mm, rotation_deg,
                                 y_floor)
        inserted.append({
            "id": "corner-%s-%s" % (corner["corner"], layer),
            "corner_cabinet": True,
            "corner": corner["corner"],
            "handed": handed,
            "layer": layer,
            "cabinet_type": "wall" if layer == "wall" else "base",
            "family": "wall" if layer == "wall" else "base",
            "width_mm": corner_size_mm,
            "depth_mm": corner_size_mm,
            "height_mm": _CORNER_HEIGHT_MM[layer],
            "zone": "wall" if layer == "wall" else "base_run",
            "wall": wall_tag,
            "run_seq": -1,
            "__pose": pose,
            "replaced_ids": [c["id"] for c in (host_first, other_cab)
                             if c is not None],
        })
        # The corner no longer consumes host_wall's run cursor by joining it
        # (it carries an explicit __pose instead), so host_wall's own
        # surviving cabinets need the SAME explicit start-offset the
        # adjoining run gets below — host_wall's low end is always at this
        # corner by construction (that's what makes it "host").
        #
        # I1: keyed by (wall, layer) — NOT just wall — so a base-layer
        # corner's offset never bleeds into that same wall's wall (upper)
        # run, and vice versa. Each detected corner is already scoped to
        # exactly one layer (`corner["layer"]`); the offset must stay
        # scoped to it too.
        offsets[(host_wall, layer)] = max(
            offsets.get((host_wall, layer), 0), corner_size_mm)
        if other_end == "first":
            # The adjoining low-end run must start past the corner footprint.
            offsets[(other_wall, layer)] = max(
                offsets.get((other_wall, layer), 0), corner_size_mm)

    final = [dict(c) for c in assigned if c["id"] not in removed_ids]
    final.extend(dict(n) for n in inserted)
    placements = layout(final, room, wall_start_offsets=offsets,
                        **layout_kwargs)

    # Cap pass — a standalone (both-high) corner reserves its cell but can't
    # push a run past it the way a low-end join does, so any standard cabinet
    # overlapping the cell is removed (replaced by that corner) and the layout
    # re-run. The overlappers are always the runs' HIGH-end cabinets, so
    # dropping them never shifts a survivor into the cell — one pass converges.
    if standalone_cells:
        place_by_id = {p["id"]: p for p in placements}
        capped = set()
        for cell, node in standalone_cells:
            for c in final:
                if c.get("corner_cabinet") or c["id"] in capped:
                    continue
                if footprints_overlap(
                        footprint_mm(c, place_by_id[c["id"]]), cell):
                    capped.add(c["id"])
                    node["replaced_ids"].append(c["id"])
        if capped:
            removed_ids |= capped
            final = [c for c in final if c["id"] not in capped]
            placements = layout(final, room, wall_start_offsets=offsets,
                                **layout_kwargs)

    # Enforced postcondition: every emitted layout is physically valid.
    # If a cabinet spilled outside the room, the walls can't hold the run —
    # fail explicitly instead of returning an unmanufacturable layout.
    by_id = {c["id"]: c for c in final}
    place_by_id = {p["id"]: p for p in placements}
    room_w = room.get("width_mm", 0)
    room_d = room.get("depth_mm", 0)
    outside = []
    for c in final:
        cid = c["id"]
        if within_room(by_id[cid], place_by_id[cid], room):
            continue
        x0, x1, z0, z1 = footprint_mm(by_id[cid], place_by_id[cid])
        overflow_mm = max(0.0, -x0, x1 - room_w, -z0, z1 - room_d)
        outside.append({"id": cid, "overflow_mm": overflow_mm,
                        "wall": by_id[cid].get("wall") or "back"})
    if outside:
        cap = wall_capacity_mm(room, wall_order)
        req = check_capacity(cabinets, room, wall_order)["requested_mm"]
        worst = max(outside, key=lambda o: o["overflow_mm"])
        detail = ("%d cabinet(s) extend past the end of their wall; "
                  "worst: id=%s overflows %.0fmm on wall=%s"
                  % (len(outside), worst["id"], worst["overflow_mm"],
                     worst["wall"]))
        raise LayoutCapacityExceeded(cap, req, detail=detail, outside=outside)

    # "assigned" — every input cabinet's post-distribution wall/run_seq,
    # INCLUDING the cabinets a corner replaced (which "cabinets" omits).
    # The ORM caller must persist wall/run_seq for the replaced-and-
    # archived cabinets too: if it doesn't, a later reset-and-restore
    # resurrects them with their PRE-distribution wall, reconstructing a
    # different (possibly overfull) run than the one this call resolved
    # — the auto-arrange idempotence break (2026-07-26).
    return {"cabinets": final, "assigned": assigned,
            "placements": placements, "corners": corners,
            "inserted": inserted, "removed_ids": sorted(removed_ids)}
