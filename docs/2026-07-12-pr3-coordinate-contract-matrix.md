# PR3 Coordinate-Contract Matrix — Renderer Punch List

**Status:** read-only analysis. No code changed.
**Basis:** `addons/southbrook_estimating/models/COORDINATE_CONTRACT.md` (v1,
2026-07-11) + its header cross-reference in `kitchen_layout_engine.py`, and
the enforcement test `addons/southbrook_kitchen_3d_configurator/tests/test_coordinate_contract.py`.
**Repo state at time of review:** branch `feat/configurator-pr2.5a-url-restore`,
clean working tree, `HEAD` identical to `main` for every file analyzed below
(`git diff main...HEAD --stat` on the relevant paths returned no output — no
divergence to reconcile). `kitchen_configurator.js` and `controllers/main.py`
are the two files flagged as under concurrent edit by another agent; they are
covered here only as flag-only context rows / evidence citations, unmodified.

## Contract recap (for matrix scoring)

World frame, millimetres internally, inches on the model, feet in the scene
(`IN = 1/12`): **+X** along the back wall (left→right), **+Y** up from the
floor, **+Z** from the back wall into the room. `rotation_deg ∈ {0,90,180,270}`
about +Y; `0`=back (faces +Z), `180`=front (faces −Z), `90`=left (faces +X),
`270`=right (faces −X). Anchor = local back-left-bottom corner. The contract
document itself already discloses two migration-debt lines (`base_cabinet`
ignores y/z; `wall_cabinet` reads z as height) — this review verifies those
plus everything else in scope, with file:line evidence.

---

## Matrix

| Component | Uses X | Uses Y | Uses Z | Uses Rotation | Violates Contract | Fix |
|---|---|---|---|---|---|---|
| `base_cabinet.esm.js` | Yes — `item.x_position_in*IN` → THREE X, world-inch convention, correct **only while back-wall-flush** | No — mesh Y always derived from own height constants (toe-kick + `cbH`), `y_position_in` never read | No — mesh Z always `cbD/2` (flush to back wall); `z_position_in` never read | No — `rotation_deg` never read | **Yes (confirmed)** — matches contract's own "Known migration debt" line and the enforcement test's debt set `{y,z,rotation}` | Rebuild in local frame (`x=0`) and delegate world x/y/z/rotation to `_placeCabinetGroup`, mirroring the pattern already used by `wall_cabinet`/`other_cabinets` |
| `wall_cabinet.esm.js` | Yes — `item.x_position_in*IN` → THREE X, correct on back wall | **Misused** — mesh Y (`wbY`) is populated from `item.z_position_in`, not `item.y_position_in`; the latter is never read | **Misused** — `z_position_in` is read but fed into the Y slot (mount-height), not into a Z (depth) slot; mesh Z is always fixed at `wbD/2` | Indirect only — when `__localFrame` (i.e. routed through `_placeCabinetGroup` for a rotated cabinet), `wbY` collapses to 0 so the group's own rotation applies; the builder itself never reads `rotation_deg` | **Yes (confirmed)** — this is the contract's other explicitly documented debt line, verbatim: "reads z_position_in as vertical height (wbY)" | Requires a **data-semantics fix first** (see Riskiest Finding below): decide which field (y or z) is canonical for mount-height, migrate the persisted data + all writers, then convert to local-frame build |
| `other_cabinets.esm.js` (`buildOtherCabinet` / `buildFillerPanel` / `buildEndCapPanel`) | Yes, all three fns — `item.x_position_in*IN` → THREE X | No for `buildOtherCabinet`/`buildEndCapPanel` (Y populated from `z0`, i.e. from `z_position_in`, same as wall_cabinet); `buildFillerPanel` has no Y logic tied to any field | **Same z-as-height pattern** for `buildOtherCabinet`/`buildEndCapPanel` (`z0 = item.z_position_in`, fed into the Y slot); `buildFillerPanel` reads `z_position_in` **not at all** — a stricter, undetected omission | No — none of the three functions read `rotation_deg` directly; rotated placement handled externally via `__localFrame` zeroing + `_placeCabinetGroup` | **Yes (confirmed)**, plus one **masked** sub-violation | `buildOtherCabinet`/`buildEndCapPanel`: same local-frame migration as wall_cabinet, gated on the same y/z semantics fix. `buildFillerPanel`: needs z/y handling added before it can ever be routed through `_placeCabinetGroup` for a non-back-wall filler |
| `room_shell.esm.js` | Room-level only (`rw`), not per-cabinet | Room-level only (`rh`) | Room-level only (`rd`) | N/A | **N/A** — no per-cabinet field consumed at all; it is room geometry, not cabinet geometry. Its wall tags (`back`/`left`/`right`/`front`, lines 56/62/69/75) correctly mirror `kitchen_layout_engine.py`'s `WALLS`/`_WALL_SPEC` | None needed |
| `drop_lanes.esm.js` | Room-level only (`rw`), no per-cabinet x | WALL lane's vertical anchor uses the `WBY` constant, not any item field | **All three lanes hardcoded to the back wall** (`z≈0` or `baseD/2`); no left/right/front lane variants exist | N/A | **Yes (confirmed KNOWN issue b/c pairing)** — drag-and-drop visual feedback is architecturally back-wall-only today | Parametrize `buildDropLanes` by target wall (mirror `_WALL_SPEC`), or precompute 4 lane-sets and toggle by active/hovered wall |
| `drop_raycaster.esm.js` (`computeDropXIn`) | Yes — the **only** axis it computes; floor-plane raycast → world-X → inches, clamped/snapped | Implicit only, as the raycast plane (`y=0`); not read/written as a field | **Not computed at all** — `hit.z` is discarded; function returns a bare number, not `{x,z}` | No | **Yes (confirmed KNOWN issue b)** — single-axis by construction; cannot report a drop point on any non-back wall | Extend to `computeDropPointIn` returning `{x, z, wall}` (or accept an `activeWall` param and raycast the matching plane) |
| `drag_handle.esm.js` (`buildDragHandle`/`buildDepthHandle`) | Room-edge relative (`rw+0.08`), not cabinet x | Fixed decorative constant (`0.18`) | Room-edge relative (`rd+0.08`) for the depth handle | No (static cone orientation, not `rotation_deg`) | **N/A** — manipulates `room.width_in`/`room.depth_in`, a different (non-contract) concern entirely | None needed |
| `pack_row.esm.js` (`packRow`) | Yes — sole field mutated: `it.x_position_in` | No | No | No | **Yes (confirmed KNOWN issue d)** — single-axis packer; correct for back/front runs where "along" = X, but the contract's along-axis for left/right walls is **Z** (`_WALL_SPEC["left"/"right"].along == "z"`); reused as-is for a side-wall run it would repack the wrong axis | Generalize to an along-axis-agnostic packer (accessor param, or translate through the wall's "along" axis before/after calling) before any left/right reuse |
| `kitchen_canvas.esm.js` (`_placeCabinetGroup` / `_needsTransform` / dispatch) | Yes, both paths (legacy delegates to builders; group path sets `grp.position.x`) | Yes, **group path only** — `grp.position.y=(it.y_position_in‖0)*IN` | Yes, **group path only** — `grp.position.z=(it.z_position_in‖0)*IN` | Yes, **group path only** — `grp.rotation.y=(it.rotation_deg‖0)*π/180` | **Yes, by design — this IS the dual path** — `_needsTransform` gates purely on `rotation_deg !== 0`; every rotation-0 (back-wall) item, even one with a genuine nonzero z/y, always takes the legacy path and never gets the contract-correct group transform | **This is PR3's actual target.** Collapse dispatch to always use `_placeCabinetGroup`, gated on the y/z semantics fix (row 2) landing first and validated against the existing golden-scene snapshot (`_sbSceneSnapshot`) as a straight-kitchen compatibility gate |
| `selection.esm.js` | No | No | No | No | **N/A** — operates purely on `item.layout_key` identity; no placement field touched | None needed |
| `view_specs.esm.js` | Room-level (`rw`) for camera math | Room-level (`rh`) | Room-level (`rd`) | No (`up` vectors static) | **N/A** for the contract, but flag: its "left"/"right" **camera views** are a naming coincidence with the layout engine's left/right **wall rotation** convention — no functional overlap, just a review-time confusion risk | Optional rename/comment only |
| `pointer_pipeline.esm.js` | `resolveRoomWidthFromDrag` operates on `room.width_in` via screen `clientX`, not cabinet x | No `y_position_in` involvement | `resolveRoomDepthFromDrag` maps screen `clientY` → `room.depth_in` (world-Z magnitude), but never touches an item's z field | No | **N/A** — room-sizing helpers, not cabinet placement. Carries its own open TODO (sign-flip risk on depth-drag, self-documented at lines 54-57) unrelated to PR3 | None required for the contract; unrelated open TODO stands |
| `mesh_factory.esm.js` (`makeMesh`) | Pass-through (`pos[0]`) | Pass-through (`pos[1]`) | Pass-through (`pos[2]`) | Pass-through (Euler triple) | **N/A** — convention-agnostic primitive; correctness lives entirely in what callers pass it | None needed — keep as the shared substrate |
| `constants.esm.js` | N/A (no per-item field) | `WBY` = `BH+CTR+GAP`, a **height** constant | N/A | N/A | **Worth flagging** — `WBY`'s existence and its role as the fallback for a *z_position_in-derived* `wbY` (wall_cabinet.esm.js:42) and as the drop-lane wall-band anchor (drop_lanes.esm.js:29/52) institutionalizes "Z-field feeds Y-position" as an implicit cross-file contract | No code change required here; rename/re-scope once row 2's y/z field fix lands, so a "Y" constant fed from a "Z" field doesn't keep misleading readers |
| `kitchen_configurator.js` (context, flag-only — concurrent edit) | Yes — `_recomputeLayoutFromItems` drives `packRow` per run and owns the inventory-drop path (`computeDropX` → single X) | Writes hardcoded `y_position_in: 0` for newly dropped wall cabinets | Writes `z_position_in: z` for new wall-cabinet drops, seeded from the last-seen server value or the literal `34.5+1.5+18.0` (= `WBY`) | Reads/writes `item.rotation_deg` for the rotate action, `% 360`, no allowed-set `{0,90,180,270}` validation client-side | **Yes — this is the CLIENT-SIDE root of the z-as-height convention**, not just a passive rendering quirk: it actively seeds new data in the same broken shape | Flag only per task scope. PR3 must migrate this file's y/z writes in lockstep with the renderer + controller, or newly dropped cabinets keep corrupting data even post-migration |
| `southbrook_customer_portal/.../kitchen_canvas.js` | No | No | No | No | **N/A — not under the contract at all.** Self-contained BOM/cutlist box visualizer using `slot.x_offset_mm` / `run.anchor_x_mm` / `run.anchor_y_mm` and fixed box W/H/D (lines 162-170); zero references to `x_position_in`/`y_position_in`/`z_position_in`/`rotation_deg` anywhere in the file (grep-confirmed) | None required; confirm it stays out of scope if ever wired to design-line data |
| `southbrook_estimating_website/.../sample_3d_widget.esm.js` | No | No | No | No | **N/A — not under the contract at all.** Standalone marketing/sample widget, own hardcoded `ROOM_W/ROOM_H/ROOM_D`, center-origin local coordinates per cabinet (e.g. line 460 `mesh.position.set(x,y,z)` from its own layout loop); zero references to the design-line placement fields (grep-confirmed) | None required; same caveat as the customer-portal row |

---

## Evidence appendix (file:line)

**`base_cabinet.esm.js`**
- L31: `const x = item.x_position_in * IN;` — only field read from `item` for placement.
- L42, L48, L59, L66, L73, L79, L86, L92, L103: every mesh's Z component is `cbD/2` (or `cbD+0.07/2`), never `item.z_position_in`.
- Height math (e.g. L48 `3.5*IN + (cbH-3.5*IN)/2`) is entirely derived from `cbH`; `item.y_position_in` string does not appear in the file.

**`wall_cabinet.esm.js`**
- L30: `const x = item.x_position_in * IN;`
- L39-42:
  ```
  const wbY = item.__localFrame ? 0
      : ((item.z_position_in != null && item.z_position_in !== 0)
          ? item.z_position_in * IN
          : WBY);
  ```
  — the exact line the contract document cites as debt.
- `item.y_position_in` does not appear anywhere in the file (0 hits).

**`other_cabinets.esm.js`**
- L35, L100, L122: `x_position_in` read in all three exported functions.
- L41: `const z0 = item.__localFrame ? 0 : (item.z_position_in || 0) * IN;` — `buildOtherCabinet`.
- L51, L56, L66: `z0` fed into the mesh's **Y** position slot, e.g. `[x+w/2, z0+3.5*IN/2, d/2]`.
- L128: identical `z0` pattern in `buildEndCapPanel`.
- `buildFillerPanel` (L99-107): no `z0`, no `item.z_position_in`, no `item.y_position_in` reference at all — a masked omission (see enforcement-test caveat below).

**`kitchen_canvas.esm.js`**
- L279-301: dispatch — `this._needsTransform(it) ? this._placeCabinetGroup(...) : push(builder(...))` repeated per cabinet-type filter.
- L447-463 (`_placeCabinetGroup`): consumes all four contract fields correctly —
  ```
  grp.position.set(
      (it.x_position_in || 0) * IN,
      (it.y_position_in || 0) * IN,
      (it.z_position_in || 0) * IN,
  );
  grp.rotation.y = ((it.rotation_deg || 0) * Math.PI) / 180;
  ```
- L465-474 (`_needsTransform` + comment): explicitly documents the reason for rotation-only gating — "on WALL cabinets z_position_in is the D8 mount height, not depth — gating on z would misfire on D8-customised back uppers." This is the code acknowledging the exact conflict this review flags as the riskiest finding.
- L412-439 (`_sbSceneSnapshot`): the golden-scene compatibility-gate harness already built for exactly this migration.

**`drop_lanes.esm.js`**
- L29: `const wallBotZ = WBY;`
- L40: `base.position.set(rw/2, 0.004, baseD/2);`
- L52: `wall.position.set(rw/2, wallBotZ + wallH/2, 0.004);`
- L68: `tall.position.set(rw - tallW/2, 3.5*IN + tallH/2, baseD/2);`
- All three fixed at/near `z≈0` (back wall) or `baseD/2`; no wall parameter anywhere in the function signature.

**`drop_raycaster.esm.js`**
- L32: `export function computeDropXIn(THREE, camera, raycaster, ndc, roomWidthIn, snapIn = 6, marginIn = 6)` — no z/wall parameter.
- L41: `let xIn = hit.x * 12;` — `hit.z`/`hit.y` computed by the raycast but never read.

**`pack_row.esm.js`**
- L19: `const sortX = (a, b) => (a.x_position_in || 0) - (b.x_position_in || 0);`
- L42, L48, L51: only `u.x_position_in` is ever written.

**`constants.esm.js`**
- L19: `export const IN = 1 / 12;`
- L28: `export const WBY = BH + CTR + GAP;` — a height, consumed cross-file from a Z-named field.

**`controllers/main.py`** (cited for data-layer confirmation only, not a matrix row)
- L126: `min_z = base_h + ctr_t + gap` (= `WBY`'s server-side twin).
- L132-138 (D8 alignment block): `wall_z` computed from `wall_cab_top_alignment` (`fixed_gap`/`to_ceiling`/`to_soffit`).
- L165-166: `items.append(self._layout_item(base, i, x, 0.0, 0.0, ...)); items.append(self._layout_item(wall, i, x, 0.0, wall_z, ...))` — **`y` is hardcoded `0.0` for wall cabinets; `wall_z` (the mount-height number) is passed as the `z` argument.** This is the server-side origin of the convention `wall_cabinet.esm.js` and `other_cabinets.esm.js` both consume.

**`kitchen_configurator.js`** (cited for data-layer confirmation only, not a matrix row beyond its context entry)
- L694-698: `z = (walls.length && walls[0].z_position_in) || (34.5 + 1.5 + 18.0);` — client-side literal reproduction of `WBY`.
- L735-736: `y_position_in: 0, z_position_in: z,` — new wall-cabinet drop items seeded with the same y=0/z=height shape.
- L1137-1138: `item.rotation_deg = (cur + 360) % 360;` — no `{0,90,180,270}` snap/validation on the client before persisting.

**Enforcement-test caveat (own limitation, not a contract violation, but relevant to PR3 planning)**
`test_coordinate_contract.py`'s `_missing()` check is a **file-level substring
search** (`f not in src`), not a per-function AST check. This means:
- `other_cabinets.esm.js` passes today because `z_position_in` appears
  *somewhere* in the file (via `buildOtherCabinet`/`buildEndCapPanel`), even
  though `buildFillerPanel` in the same file never reads it — a real,
  currently undetected gap.
- `kitchen_canvas.esm.js`'s `test_central_placement_consumes_all_fields`
  passes because all four field-name strings appear in the file, but this
  cannot (by construction) distinguish the contract-correct `_placeCabinetGroup`
  branch from the still-noncompliant legacy branch that the same file also
  contains. The test is a true positive for "the fields are read somewhere,"
  not "every placement path is compliant."
Recommend strengthening both checks as part of PR3 (function-scoped or
dispatch-path-scoped assertions), but this is not a blocker for starting the
migration — it is a gap in the safety net, not in the renderer.

---

## PR3 sequencing recommendation

### Blockers (must land before the dual-path collapse)

1. **Resolve the y/z field-semantics conflict for wall-mounted cabinets first.**
   This is the actual root cause, and it is a **data + writer** problem, not
   a renderer problem: `controllers/main.py` (`_layout_item`, L165-166) and
   `kitchen_configurator.js` (L694-736) both currently persist wall-cabinet
   mount-height into `z_position_in` while hardcoding `y_position_in: 0`.
   Flipping `_needsTransform` to always use `_placeCabinetGroup` *before*
   this is fixed will silently misplace every migrated wall cabinet: its
   real depth-into-room offset would come from a field that actually holds
   a mount-height number (e.g. 54"), placing it 54" into the room instead of
   flush to its wall, while its true elevation (which lives nowhere) defaults
   to 0 (floor level). This must be a coordinated migration: pick the
   canonical field, backfill/migrate persisted `southbrook.kitchen.design.line`
   + mirrored `sale.order.line` rows, and update both writers, before any
   renderer flip.
2. **`drop_raycaster.esm.js` + `drop_lanes.esm.js` wall-awareness.** Neither
   can currently produce or visualize a correct placement for anything other
   than the back wall — drag-and-drop onto left/right/front walls has no
   data path today, independent of the renderer fix.
3. **`pack_row.esm.js` along-axis generalization** before it is ever reused
   for a left/right-wall run (today it would silently write into
   `x_position_in` for a run whose along-axis is actually `z`).

### Non-blockers / cosmetic (no PR3 code change required)

`room_shell.esm.js`, `drag_handle.esm.js`, `selection.esm.js`,
`view_specs.esm.js` (naming-caveat only), `mesh_factory.esm.js`,
`pointer_pipeline.esm.js`, `constants.esm.js` (rename-only, deferred), and
both "other renderers" (`southbrook_customer_portal/kitchen_canvas.js`,
`sample_3d_widget.esm.js` — confirmed structurally out of scope, no contract
fields consumed at all).

### Suggested order

1. Land the y/z field-semantics decision + data migration (blocker 1) —
   everything else depends on it.
2. Migrate `base_cabinet.esm.js` to local-frame + `_placeCabinetGroup` first
   among the builders — it currently ignores y/z entirely, so it carries the
   *least* semantic risk (no field to un-misuse, just a mechanical move).
3. Migrate `wall_cabinet.esm.js` and `other_cabinets.esm.js`'s
   `buildOtherCabinet`/`buildEndCapPanel` together once step 1 lands (same
   z-as-height pattern, same fix).
4. Fix `buildFillerPanel`'s masked total omission of z/y handling — currently
   invisible to the enforcement test, and would otherwise become the last
   back-wall-only holdout after step 3.
5. Flip `_needsTransform` to always route through `_placeCabinetGroup`,
   gated on the golden-scene snapshot (`_sbSceneSnapshot`, already built for
   this) matching for existing straight (rotation-0) kitchens before/after.
6. Only after the renderer is unified: extend `drop_raycaster`/`drop_lanes`/
   `pack_row` for real non-back-wall drag-and-drop. This is new capability,
   not a contract conformance fix, and should trail the renderer work rather
   than gate it.
7. Strengthen `test_coordinate_contract.py` from file-level substring checks
   to function/dispatch-path-scoped checks so the two masked gaps identified
   above (buildFillerPanel; kitchen_canvas legacy branch) become visible to
   the test suite going forward.

### Single riskiest finding

The z-as-height convention for wall cabinets is not a renderer quirk — it is
baked into the **persisted data model** via `controllers/main.py`'s
`_layout_item` (`y=0.0`, `z=wall_z`) and re-seeded on every new client-side
drop via `kitchen_configurator.js` (L694-736, literally reproducing `WBY` as
a fallback `z_position_in`). Any PR3 change that flips `_needsTransform` or
otherwise routes wall cabinets through the contract-correct
`_placeCabinetGroup` path *without* first migrating this data and both
writers will silently render every affected wall cabinet at the wrong depth
(using its mount-height number as a Z-offset into the room) and at floor
level (Y defaults to the never-populated 0) — a correctness regression that
would ship invisibly because the enforcement test only checks for field-name
presence, not placement correctness.
