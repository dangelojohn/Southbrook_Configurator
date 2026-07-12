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

## Known migration debt (2026-07-11)

The renderer does NOT yet conform to this contract:
- `base_cabinet.esm.js` ignores `y_position_in` and `z_position_in`.
- `wall_cabinet.esm.js` reads `z_position_in` as vertical height (`wbY`).

The coordinate-model-unification work migrates every builder to this
contract (and adds `THREE.Group` rotation). Until then, multi-wall layouts
render incorrectly even though the underlying data is valid per this
contract. This debt is tracked and must be paid before U-shape ships to
users.
