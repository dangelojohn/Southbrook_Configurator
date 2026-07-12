# Add-a-Cabinet Sequence — the one-page mental model

**Status: normative reference.** How one cabinet travels from a click to a rendered mesh.
If a future change makes any arrow below skip a stage or compute geometry in the wrong
layer, it is breaking the architecture. Companion to `2026-07-12-renderer-contract.md`
(who-owns-what) and `2026-07-12-canonical-coordinate-flow.md` (the field table).

```
   User clicks a wall in the 3D room
            │                       KitchenCanvas raycasts the wall mesh,
            ▼                       fires onWallSelect(wall)  (mechanics live in the canvas)
   state.activeWall = "left"        configurator owns this UI state only
            │
            ▼
   User adds a cabinet              _addCabinetFromProduct: new item, wall = activeWall
            │
            ▼
   ┌─────────────────────────┐      ── PR4: this is the new arrow ──
   │  layout engine           │     backend asks kitchen_layout_engine.layout(cabs, room)
   │  _place_on_wall(...)      │     for the cabinet's wall — the ENGINE decides the pose
   └─────────────────────────┘
            │
            ▼
   (x, y, z, rotation_deg)          x = along-wall · y = elevation · z = depth · rot about +Y
            │
            ▼
   save_design  ──►  design.line    CANONICAL MODEL: pose persisted exactly, lossless
            │
            ▼
   load_design_lines                on reopen, hydrate items from the model
            │                       (never regenerate — PR2.5)
            ▼
   KitchenConfigurator.state.items  configurator holds the items; owns no geometry
            │
            ▼
   KitchenCanvas._placeCabinetGroup  the SINGLE render path (PR3.1)
            │                        builds local geometry, applies the given pose
            ▼
   THREE.Group  position=(x,y,z)·IN, rotation.y=rotation_deg
            │
            ▼
   Mesh  drawn where it was told — no inference, no repack
```

## What is deliberately absent from this sequence (and must stay absent)
- **No wall math in JavaScript.** The client never computes a side-wall cabinet's
  x/z/rotation — it asks the engine (the PR4 arrow) and persists the answer.
- **No renderer calculation.** `_placeCabinetGroup` *applies* the pose; it never derives it.
- **No duplicated coordinate transforms.** One engine, one canonical model, one render path.
- **No client repack for non-back walls.** `packRow`'s single-axis packing is legacy; PR4
  yields wall-item geometry to the engine rather than extending it.

## The two surfaces share this sequence
The website 3D tab already implements the engine arrow (`_sb_place_line_on_wall` →
`kitchen_layout_engine.layout`). PR4 brings the backend configurator onto the same path —
ideally via a shared helper, so there is one add-a-cabinet sequence, not two.
