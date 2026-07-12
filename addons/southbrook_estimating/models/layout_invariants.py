# SPDX-License-Identifier: LGPL-3.0-only
"""Topology-agnostic invariants for kitchen layouts.

These hold for EVERY layout the engine emits — straight, L, U, G, island,
peninsula — so each new topology reuses them instead of rewriting scenario
assertions. Pure (no Odoo). Each check returns a list of human-readable
violation strings; empty list == invariant holds. See COORDINATE_CONTRACT.md.
"""
try:
    from . import kitchen_layout_engine as E
except ImportError:                       # offline / bare python3
    import kitchen_layout_engine as E


def _by_place(result):
    return {p["id"]: p for p in result["placements"]}


def check_within_room(result, room):
    pl = _by_place(result)
    return ["cabinet %r outside room" % c["id"]
            for c in result["cabinets"]
            if not E.within_room(c, pl[c["id"]], room)]


def _yrange(cab, place):
    y0 = place.get("y", 0)
    return (y0, y0 + cab.get("height_mm", 0))


def check_no_overlaps(result):
    """3D overlap: two cabinets collide only if their X/Z footprints AND
    their Y (height) ranges intersect. Base cabinets (y≈0) and wall/upper
    cabinets (y≈1400) may share an X/Z footprint — they're stacked, not
    colliding — so the Y check is essential."""
    pl = _by_place(result)
    boxes = [(c["id"], E.footprint_mm(c, pl[c["id"]]), _yrange(c, pl[c["id"]]))
             for c in result["cabinets"]]
    out = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ia, fa, ya), (ib, fb, yb) = boxes[i], boxes[j]
            if (E.footprints_overlap(fa, fb)
                    and ya[0] < yb[1] - 1 and yb[0] < ya[1] - 1):
                out.append("overlap %r & %r" % (ia, ib))
    return out


def check_rotations(result):
    return ["rotation %s not in %s on %r"
            % (p["rotation_deg"], E.ALLOWED_ROTATIONS, p["id"])
            for p in result["placements"]
            if int(round(p["rotation_deg"])) % 360 not in E.ALLOWED_ROTATIONS]


def check_wall_assignments(result):
    return ["wall %r invalid on %r" % (c.get("wall"), c["id"])
            for c in result["cabinets"]
            if (c.get("wall") or "back") not in E.WALLS]


def check_count_conserved(input_count, result):
    survivors = input_count - len(result["removed_ids"])
    expected = survivors + len(result["inserted"])
    if len(result["cabinets"]) != expected:
        return ["count not conserved: final=%d, expected survivors(%d)+"
                "corners(%d)=%d" % (len(result["cabinets"]), survivors,
                                    len(result["inserted"]), expected)]
    return []


def check_corner_structure(result):
    valid = {frozenset(walls) for _name, walls, _pos in E._CORNER_SPECS}
    out = []
    for corner in result["corners"]:
        walls = corner["walls"]
        if len(set(walls)) != 2 or frozenset(walls) not in valid:
            out.append("corner %r has invalid adjacent walls %r"
                       % (corner.get("corner"), walls))
    return out


def check_unique_ids(result):
    ids = [c["id"] for c in result["cabinets"]]
    return [] if len(ids) == len(set(ids)) else ["duplicate cabinet ids"]


def check_all(result, input_count, room):
    """Run every invariant. Returns {name: [violations...]} for any that
    failed (empty dict == all pass)."""
    checks = {
        "within_room":      check_within_room(result, room),
        "no_overlaps":      check_no_overlaps(result),
        "rotations":        check_rotations(result),
        "wall_assignments": check_wall_assignments(result),
        "count_conserved":  check_count_conserved(input_count, result),
        "corner_structure": check_corner_structure(result),
        "unique_ids":       check_unique_ids(result),
    }
    return {k: v for k, v in checks.items() if v}
