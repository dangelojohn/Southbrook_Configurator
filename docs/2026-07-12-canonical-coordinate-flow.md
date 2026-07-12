# Canonical Coordinate Flow — Southbrook Kitchen Configurator (after PR3.1)

**Purpose:** the single authoritative coordinate pipeline, so PR4/PR5 placement work has one
contract to build against. Design note only — no implementation. Companion to
`COORDINATE_CONTRACT.md` (the geometry spec) and the PR3 matrix
(`2026-07-12-pr3-coordinate-contract-matrix.md`).

## The one pipeline (after PR3.1 collapses the renderer dispatch)

```
  kitchen_layout_engine        pure geometry: (wall, run_seq) → world (x,y,z,rotation_deg)
        │                      [authoritative for auto-arrange / corners / L·U·G]
        ▼
  _layout_item / auto_arrange  write layout-domain fields onto the design line
        │                      (backend /layout fill also writes here; interactive drop too)
        ▼
  southbrook.kitchen.design.line   THE CANONICAL MODEL (per-cabinet placement fields)
        │        ▲
   save_design   │ load_design_lines        one shared read/write contract; both carry
        │        │ (+ room, design_name)     x/y/z/rotation_deg/wall/run_seq
        ▼        │
  KitchenConfigurator (OWL)     state.items ⇄ the model; owns activeWall (UI), no geometry
        │
        ▼
  KitchenCanvas._placeCabinetGroup   the SINGLE render path (PR3.1): builds each cabinet in a
        │                            LOCAL frame (x=0) then applies the world transform
        ▼
  THREE.Group   position=(x,y,z)·IN, rotation.y=rotation_deg          (IN = 1/12 scene-feet)
        │
        ▼
  Mesh          builder-local geometry only; never bakes an absolute world position

  ── side branch, NOT the render path ──
  reconcile.py → sale.order.line (sb_layout_* mm mirror)   manufacturing; see BACKLOG B6
```

## The one field table (per design line / per `state.items` entry)

| Field | Meaning | Units | Notes |
|---|---|---|---|
| `x_position_in` | position **along** the cabinet's wall | inches | back/front walls advance in world +X; left/right in world +Z (engine's `_WALL_SPEC.along`) |
| `y_position_in` | **elevation** — floor → cabinet bottom | inches | 0 = floor-standing (base/tall); wall/upper carry mount height (~54″). **Canonical since PR3.0** |
| `z_position_in` | **depth from the wall** into the room | inches | 0 = flush to its wall. (Was misused as mount-height pre-PR3.0; migrated 19.0.5.18.0) |
| `rotation_deg` | rotation about world **+Y** | degrees | back=0, front=180, left=90, right=270; 0 faces out of the back wall |
| `wall` | which room wall the cabinet is on | enum | `back` / `left` / `right` / `front` (island/peninsula generalize later — see matrix §4) |
| `run_seq` | order within that wall's run | int | engine orders a run by `(run_seq, input index)` |

## Invariants (what every stage must preserve)

1. **One render path.** After PR3.1 every cabinet (any wall, any rotation) is placed by
   `_placeCabinetGroup`; builders emit local geometry only. There is no back-wall special case.
2. **The model is authoritative.** The editor reopens by *reading* the canonical lines
   (`load_design_lines`), never by regenerating (`/layout` is empty-room suggest only). PR2.5.
3. **y = elevation, z = depth.** No stage may reintroduce z-as-height (PR3.0 fixed all writers;
   the upgraded `test_coordinate_contract.py` asserts *placement*, not field presence).
4. **Engine owns geometry; Odoo owns identity.** The pure engine tags corner nodes
   semantically; the Odoo layer maps them to SKUs. Product identity stays out of the engine.

## Deliberately NOT yet unified (tracked, for PR4+)
- `drop_raycaster` (single back-wall X) + `drop_lanes` (back-wall-only) → wall-aware in PR4.
- `pack_row` packs by `x_position_in` only → along-axis-agnostic in PR4.
- `reconcile.py` mirror flattens to one wall (B6) — manufacturing-correctness for multi-wall.
