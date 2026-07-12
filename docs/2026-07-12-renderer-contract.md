# Renderer Contract — Southbrook Kitchen Configurator

**Status: normative.** A permanent responsibility charter for the 3D layer. Written before
PR4 (wall-aware placement) so that placement work cannot re-introduce the coupling six PRs
just removed. Companion to `2026-07-12-canonical-coordinate-flow.md` (the pipeline) and
`COORDINATE_CONTRACT.md` (the geometry spec).

## Layer responsibilities — each owns exactly one thing

| Layer | Responsibility | Must NOT |
|---|---|---|
| **Engine** (`kitchen_layout_engine.py`) | **Decide** the canonical pose: given (wall, run_seq) + room, produce `(x, y, z, rotation_deg)` and corner resolution | know about SKUs, rendering, or Odoo |
| **Placement** (auto-arrange / add / drop → the engine) | **Choose** which cabinets go where, then delegate pose to the engine | compute geometry itself |
| **Persistence** (`save_design` / `load_design_lines` / the canonical `design.line`) | **Preserve** the pose exactly, round-trip lossless | transform, default, or reinterpret pose fields |
| **Renderer** (`KitchenCanvas` / `_placeCabinetGroup` / builders) | **Consume** the pose exactly and draw it | *(see the four prohibitions below)* |
| **Manufacturing** (`reconcile.py` → `sale.order.line`) | Mirror the model for BOM/cutlist | depend on anything the renderer does |

## The Renderer shall NEVER

1. **Infer `wall`.** The wall is given (`item.wall`). The renderer never guesses it from
   position, rotation, or geometry.
2. **Infer height/elevation.** Elevation is `y_position_in` (given). The renderer never
   derives mount height from `cabinet_type`, `z`, or a fallback *except* the single
   documented `WBY` default when `y` is genuinely absent — and that default is applied
   identically in both build branches (`wall_cabinet.esm.js` complement, PR3.1).
3. **Infer `rotation_deg`.** Rotation is given. The renderer applies it (`grp.rotation.y`);
   it never computes it from the wall or anything else.
4. **Repack / relayout.** The renderer places each cabinet at its given `(x,y,z,rotation)`
   and stops. It does not sort, pack, offset, snap, or resolve corners. Layout is the
   engine's job (`packRow`'s single-axis packing is legacy and slated to retire into the
   engine — see the coordinate matrix §4 and B-list).

> **One-line test:** if a renderer function reads any field to *decide* a coordinate rather
> than to *apply* one, it is violating this contract.

## Consequence for PR4 (wall-aware placement) — the load-bearing rule

**PR4 must not decide geometry in the UI.** The flow is, and stays:

```
   activeWall (UI intent)
        ↓
   layout engine            ← decides (x,y,z,rotation) for the chosen wall
        ↓
   canonical items          ← persisted pose
        ↓
   renderer                 ← draws what it is given (already correct after PR3.1)
```

The renderer is already done for multi-wall (`_placeCabinetGroup` honors any wall's pose).
So PR4 is a *placement/persistence* change (route a drop/add to the engine for the active
wall; persist the returned pose), **not** a renderer change. The temptation will be to
compute a side-wall cabinet's x/z/rotation inside `kitchen_configurator.js` or the drop
handler — **don't.** That client-side geometry is exactly the coupling PR1–PR3.1 removed.
`drop_raycaster`/`drop_lanes`/`packRow` becoming wall-aware means *feeding the engine the
right wall + along-position*, not reimplementing `_place_on_wall` in JS.

## Enforcement
- `tests/test_coordinate_contract.py` asserts placement semantics (not field presence) —
  PR3.0.
- `tests/golden/design83.snapshot.json` pins byte-identical renderer output — PR3.1;
  PR3a wires it into an automated regression run.
- Any PR that makes the renderer read a field to *decide* a coordinate should fail review
  against prohibitions 1–4 above.
