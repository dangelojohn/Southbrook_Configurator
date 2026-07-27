# Southbrook Kitchen — Design-Line Coordinate Contract

**Status:** normative. Version 1 (2026-07-11).
**Audience:** the layout engine, persistence (`southbrook.kitchen.design.line`
+ mirrored `sale.order.line`), the 3D renderer (`canvas/*_cabinet.esm.js`),
and any future importer/exporter.

This document is the single authoritative definition of what a design
line's placement fields mean. It exists so that no builder or consumer ever
re-invents the semantics (e.g. treating `z_position_in` as "height"). If you
are changing any code that reads or writes these fields, this contract wins;
update the contract *first*, in a reviewed change, if the model must evolve.

---

## World frame (right-handed, millimetres internally; fields stored in inches)

- **+X** — runs left→right along the **back wall**. Origin `x=0` is the
  back-left room corner.
- **+Y** — vertical elevation, up, measured **from the finished floor**
  (`y=0` is the floor).
- **+Z** — perpendicular distance **from the back wall face into the room**.
  Origin `z=0` is the back wall; `z = room depth` is the front of the room.

A cabinet at `rotation_deg = 0` faces **out of the back wall, toward the
room** (i.e. its door faces +Z).

## Placement fields on `southbrook.kitchen.design.line`

| Field | Meaning | Units |
|---|---|---|
| `x_position_in` | Cabinet anchor on the **X** world axis | inches |
| `y_position_in` | Cabinet anchor elevation on the **Y** world axis (floor for base, mount height for wall/upper) | inches |
| `z_position_in` | Cabinet anchor on the **Z** world axis (perpendicular from back wall) | inches |
| `rotation_deg`  | Rotation about **+Y** in world space | degrees |

**Anchor point:** the cabinet's **back-left-bottom corner** in its own local
frame (before rotation) is placed at `(x_position_in, y_position_in,
z_position_in)`. The cabinet then extends +X by width, +Y by height, +Z by
depth in its local frame, and that local frame is rotated about +Y by
`rotation_deg` around the anchor.

**`rotation_deg` allowed set:** `{0, 90, 180, 270}`.
- `0`   — back wall  (runs +X, faces +Z)
- `180` — front wall (runs +X, faces −Z)
- `90`  — left wall  (runs +Z, faces +X)
- `270` — right wall (runs +Z, faces −X)

## Mandatory consumer rules

Every cabinet mesh builder and every layout consumer **MUST**:
1. consume `x_position_in`, `y_position_in`, `z_position_in`, and
   `rotation_deg` as defined above;
2. NOT reinterpret any field (no "z means height", no ignoring y/z);
3. treat the anchor as the local back-left-bottom corner;
4. apply `rotation_deg` as a world +Y rotation about the anchor.

## Engine postconditions (enforced — see kitchen_layout_engine)

Every layout the engine emits is **physically valid**:
- every cabinet lies within the room bounds `[0,W] × [0,D]` (footprint,
  post-rotation);
- no two cabinets' footprints overlap;
- `rotation_deg ∈ {0,90,180,270}`;
- `wall ∈ {back, front, left, right}`.

If cabinets cannot fit the available walls, the engine raises
`LayoutCapacityExceeded` rather than emitting an overflowing (invalid)
layout. Consumers may rely on "if it returned, it is valid."

## Engine-internal vs. persisted convention (2026-07-26)

`kitchen_layout_engine.py`'s INTERNAL placements (as emitted by `layout()` /
`resolve_and_layout()` and consumed by `footprint_mm`) use a different
along-wall anchor than the one this contract defines above:

- **Engine-internal convention:** the along-wall axis coordinate is the
  cabinet's **CENTRE** (`footprint_mm`, `_place_on_wall`) — i.e. `x` (or `z`
  on left/right walls) is the midpoint of the run-facing edge, not a corner.
  This is deliberate: it is what makes the run-cursor arithmetic in
  `_place_on_wall` simple, and it is purely an engine-internal bookkeeping
  choice.
- **Persisted convention (this contract):** the back-left-bottom corner
  anchor described above.

These are NOT the same point, and the engine's raw output must never be
written to `southbrook.kitchen.design.line` / `sale.order.line` (or handed to
the renderer) as-is — doing so shifts every cabinet by half its width along
its wall. The conversion happens **exactly once**, at the ORM write boundary,
via `anchor_pose_mm(cab, place)` (in `kitchen_layout_engine.py`, alongside
`footprint_mm`). `footprint_from_anchor_mm(cab, place)` is the anchor-side
sibling of `footprint_mm`, for validating already-persisted (anchor-
convention) poses — e.g. `footprint_from_anchor_mm(cab, anchor_pose_mm(cab,
place)) == footprint_mm(cab, place)` for every placement the engine emits.

Every ORM-facing writer/reader (design-line seeding, the 3D payload builder,
any future importer) MUST call `anchor_pose_mm` on the engine's raw output
before persisting or rendering it. `footprint_mm` / `within_room` /
`footprints_overlap` inside the engine continue to operate on the
engine-internal (centred) convention, since that is the convention the
engine's own placements are already in — do not feed persisted (anchor)
poses into `footprint_mm`; use `footprint_from_anchor_mm` for those instead.

## Known migration debt (2026-07-11)

The renderer does NOT yet conform to this contract:
- `base_cabinet.esm.js` ignores `y_position_in` and `z_position_in`.
- `wall_cabinet.esm.js` reads `z_position_in` as vertical height (`wbY`).

The coordinate-model-unification work migrates every builder to this
contract (and adds `THREE.Group` rotation). Until then, multi-wall layouts
render incorrectly even though the underlying data is valid per this
contract. This debt is tracked and must be paid before U-shape ships to
users.
