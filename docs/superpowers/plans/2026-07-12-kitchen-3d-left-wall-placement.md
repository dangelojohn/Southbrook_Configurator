# Kitchen 3D Configurator — Left-Wall Cabinet Placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users add and place cabinets on the **left wall** of the 3D KitchenCanvas (today only the back wall accepts cabinets), with a discoverable **Auto / Back / Left** wall selector that defaults to auto nearest-wall.

**Architecture:** The placement pipeline is single-axis end-to-end today: the raycaster returns one scalar (back-wall X), design lines store `x_position_in`, `reconcile.py` maps everything to one `southbrook.room.wall`, and mesh builders position cabinets in absolute world coords along +X with depth in +Z. This plan adds a second (left) axis at every stage: a `wall_side` field on the design line, a left-wall drop-lane + nearest-wall raycaster, a `THREE.Group` reparent-and-rotate step so left-wall cabinets sit at X≈0 spanning Z, a per-run layout packer, a Back/Left/Auto toggle, and a second `southbrook.room.wall` in reconcile. MVP covers **base + wall** cabinet types on the left wall; tall/corner/filler/panel on the left wall are an explicit follow-up.

**Tech Stack:** Odoo 19 CE (Python models + migration), OWL components, THREE.js (vendored), `mesh_factory.makeMesh`.

## Global Constraints

- Odoo **19.0 CE** only. No Enterprise deps.
- Additive schema only. New `wall_side` column defaults to `'back'` so all existing designs render exactly as today (zero visual regression on back-wall-only kitchens).
- OWL expressions must obey the repo's `lint-owl-expr.py` pre-commit hook (no Python `or`/`and`/`not`, no JS regex literals in `t-*` attributes). See `[[owl_tokenizer_constraints]]`.
- Coordinate system (from `room_shell.esm.js`): origin at back-left floor corner. **X** runs along the back wall (0→room_width). **Z** runs along the left wall (0→room_depth). **Y** is vertical. Back wall = XY plane at Z=0 (normal +Z). Left wall = YZ plane at X=0 (normal +X). `IN = 1/12` scene-feet per inch.
- Scope: **base** and **wall** cabinet types get full left-wall support in this plan. `tall`, `corner`, `filler`, `panel` remain back-wall-only for now and MUST be documented as such (a left-wall drop of an out-of-scope type falls back to back-wall placement, never silently vanishes).
- Every substantive change ends with a smoke test + code review (repo convention).

---

### Task 1: Add `wall_side` field to the design line + migration

**Files:**
- Modify: `addons/southbrook_kitchen_3d_configurator/models/kitchen_design.py` (design.line class, near `rotation_deg` at ~1518)
- Create: `addons/southbrook_kitchen_3d_configurator/migrations/<new_version>/pre-migration.py`
- Modify: `addons/southbrook_kitchen_3d_configurator/__manifest__.py` (version bump)
- Test: `addons/southbrook_kitchen_3d_configurator/tests/test_left_wall_reconcile.py` (created in Task 7; field asserted there)

**Interfaces:**
- Produces: `southbrook.kitchen.design.line.wall_side` — `fields.Selection([('back','Back Wall'),('left','Left Wall')], default='back', required=True, copy=True)`.

- [ ] **Step 1: Add the field**

In `kitchen_design.py`, immediately after the `rotation_deg` field (~1524) add:

```python
    wall_side = fields.Selection(
        selection=[
            ("back", "Back Wall"),
            ("left", "Left Wall"),
        ],
        string="Wall",
        default="back",
        required=True,
        copy=True,
        help="Which room wall this cabinet is mounted on. Back-wall cabinets "
             "are positioned along X (x_position_in); left-wall cabinets along "
             "Z (z_position_in). Set by the 3D configurator's wall selector.",
    )
```

- [ ] **Step 2: Bump manifest version + register migration dir**

In `__manifest__.py` bump the `version` string (e.g. `5.0.3` → `5.1.0`). Note the exact new version — the migration folder MUST match it.

- [ ] **Step 3: Write the additive migration** (defensive; `required=True` selection needs a non-null backfill for existing rows)

Create `migrations/<version>/pre-migration.py`:

```python
def migrate(cr, version):
    # Additive: existing configurator/manual lines are all back-wall.
    cr.execute("""
        ALTER TABLE southbrook_kitchen_design_line
        ADD COLUMN IF NOT EXISTS wall_side varchar
    """)
    cr.execute("""
        UPDATE southbrook_kitchen_design_line
        SET wall_side = 'back'
        WHERE wall_side IS NULL
    """)
```

- [ ] **Step 4: Verify field loads**

Run a `-u southbrook_kitchen_3d_configurator` cold-upgrade on a clone DB (see `[[southbrook_v19cr_local_test_recipe]]`). Expected: upgrade completes, no `UndefinedColumn`, `wall_side` present on `southbrook.kitchen.design.line`.

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_kitchen_3d_configurator/models/kitchen_design.py \
        addons/southbrook_kitchen_3d_configurator/migrations \
        addons/southbrook_kitchen_3d_configurator/__manifest__.py
git commit -m "feat(3d): add wall_side field to design line (back/left)"
```

---

### Task 2: Left-wall drop lanes

**Files:**
- Modify: `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/drop_lanes.esm.js`
- Test: manual visual (lanes are decorative; no unit test framework for THREE meshes here)

**Interfaces:**
- Consumes: `buildDropLanes(THREE, scene, rw, rh)` — extend signature to `buildDropLanes(THREE, scene, rw, rh, rd)`.
- Produces: return object gains a `leftWall` mesh (and optionally `leftBase`) mirroring the back-wall `wall`/`base` lanes onto the left wall.

- [ ] **Step 1: Extend the builder to take room depth and add left-wall lanes**

Change the signature to accept `rd` and, after the existing `tall` lane, add left-wall equivalents. A left-wall lane is a plane rotated +90° about Y, seated at X≈0, spanning Z (0→rd):

```javascript
export function buildDropLanes(THREE, scene, rw, rh, rd) {
    const wallH    = 30 * IN;
    const baseD    = 24 * IN;
    const wallBotZ = WBY;
    // ...existing base / wall / tall lanes unchanged...

    // LEFT-WALL BASE lane — floor band hugging the left wall, full depth
    const leftBase = new THREE.Mesh(
        new THREE.PlaneGeometry(rd, baseD),
        new THREE.MeshBasicMaterial({
            color: 0x1866d4, transparent: true, opacity: 0.0,
            side: THREE.DoubleSide, depthWrite: false,
        }),
    );
    leftBase.rotation.x = -Math.PI / 2;   // lie flat on floor
    leftBase.rotation.z = Math.PI / 2;    // run along Z
    leftBase.position.set(baseD / 2, 0.004, rd / 2);
    leftBase.visible = false;
    scene.add(leftBase);

    // LEFT-WALL upper lane — vertical band on the left-wall plane at wall-cab height
    const leftWall = new THREE.Mesh(
        new THREE.PlaneGeometry(rd, wallH),
        new THREE.MeshBasicMaterial({
            color: 0x1e9e6a, transparent: true, opacity: 0.0,
            side: THREE.DoubleSide, depthWrite: false,
        }),
    );
    leftWall.rotation.y = Math.PI / 2;    // face into room (+X)
    leftWall.position.set(0.004, wallBotZ + wallH / 2, rd / 2);
    leftWall.visible = false;
    scene.add(leftWall);

    return { base, wall, tall, leftBase, leftWall };
}
```

- [ ] **Step 2: Update the caller signature**

In `kitchen_canvas.esm.js:262`, pass `rd`:

```javascript
this.T.laneMeshes = buildDropLanes(THREE, scene, rw, rh, rd);
```

- [ ] **Step 3: Verify lanes render on hover**

Load the configurator, start dragging a base cabinet. Expected: the left-wall floor band and vertical band highlight alongside the back-wall lanes (visibility wired in Task 4).

- [ ] **Step 4: Commit**

```bash
git add addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/drop_lanes.esm.js \
        addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/kitchen_canvas.esm.js
git commit -m "feat(3d): left-wall drop lanes"
```

---

### Task 3: Nearest-wall drop raycaster

**Files:**
- Modify: `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/drop_raycaster.esm.js`
- Test: `addons/southbrook_kitchen_3d_configurator/static/tests/drop_raycaster.test.js` if a JS test harness exists; otherwise assert the pure math inline via a node scratch check and document.

**Interfaces:**
- Consumes: existing `computeDropXIn(THREE, camera, raycaster, ndc, roomWidthIn, snapIn, marginIn)` — keep for back-compat.
- Produces: `computeDropTarget(THREE, camera, raycaster, ndc, roomWidthIn, roomDepthIn, forcedWall, snapIn=6, marginIn=6)` → `{ wall_side: 'back'|'left', pos_in: number } | null`. `forcedWall` is `null` (auto) | `'back'` | `'left'`.

- [ ] **Step 1: Write the failing test** (pure geometry — no THREE needed if you stub raycaster)

```javascript
// Given a floor hit at (x=10in, z=40in), auto mode picks the nearer wall.
// hit.z(40) > hit.x(10) → closer to LEFT wall (X=0) → wall_side 'left', pos = snap(z)
// A stub raycaster whose ray.intersectPlane writes hit=(10/12,0,40/12) scene-feet.
```

Write `test_computeDropTarget_auto_picks_nearest_wall` asserting `{wall_side:'left', pos_in:42}` for that hit (40 snaps to 42 on the 6" grid) and `{wall_side:'back', pos_in:12}` when hit=(x=10,z=2).

- [ ] **Step 2: Run it, verify it fails** (`computeDropTarget is not a function`).

- [ ] **Step 3: Implement**

```javascript
export function computeDropTarget(THREE, camera, raycaster, ndc, roomWidthIn,
                                  roomDepthIn, forcedWall = null,
                                  snapIn = 6, marginIn = 6) {
    if (!camera || !raycaster || !THREE) return null;
    raycaster.setFromCamera(ndc, camera);
    const floor  = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const hit    = new THREE.Vector3();
    if (!raycaster.ray.intersectPlane(floor, hit)) return null;
    const xIn = hit.x * 12;
    const zIn = hit.z * 12;
    // Decide wall: forced overrides; else nearest wall by perpendicular
    // distance (distance to back wall = zIn; distance to left wall = xIn).
    let wall = forcedWall;
    if (wall !== "back" && wall !== "left") {
        wall = (zIn <= xIn) ? "back" : "left";
    }
    if (wall === "back") {
        const maxX = Math.max(0, roomWidthIn - marginIn);
        const p = Math.max(0, Math.min(maxX, xIn));
        return { wall_side: "back", pos_in: Math.round(p / snapIn) * snapIn };
    }
    const maxZ = Math.max(0, roomDepthIn - marginIn);
    const p = Math.max(0, Math.min(maxZ, zIn));
    return { wall_side: "left", pos_in: Math.round(p / snapIn) * snapIn };
}
```

- [ ] **Step 4: Run test, verify pass.**

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/drop_raycaster.esm.js
git commit -m "feat(3d): nearest-wall drop raycaster (computeDropTarget)"
```

---

### Task 4: Wire the canvas — lane visibility, drop-target API, move handler

**Files:**
- Modify: `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/kitchen_canvas.esm.js`

**Interfaces:**
- Consumes: `computeDropTarget` (Task 3), `props.forcedWall` (Task 6), `leftBase`/`leftWall` lanes (Task 2).
- Produces: the imperative `computeDropTarget(ev)` on the canvas API the parent calls; `onMoveItem` payload gains `wall_side` + `z_position_in`.

- [ ] **Step 1: Lane visibility** — in `_updateLaneVisibility` (~270) show the left-wall lanes with the same hi/lo opacity rule as their back-wall twins:

```javascript
        lanes.leftBase.visible = show;
        lanes.leftWall.visible = show;
        if (show) {
            lanes.leftBase.material.opacity = baseHi ? 0.42 : 0.14;
            lanes.leftWall.material.opacity = wallHi ? 0.42 : 0.14;
        }
```

- [ ] **Step 2: Replace `_computeDropX` with a target-returning method** used by both drop and move:

```javascript
    _computeDropTarget(ev) {
        const room = this.props.room || {};
        return computeDropTarget(
            this.T.THREE, this.T.activeCamera, this.T.raycaster,
            this._ndcFromEvent(ev),
            room.width_in || 0, room.depth_in || 0,
            this.props.forcedWall || null,
        );
    }
```

Keep a thin `_computeDropX(ev)` returning `this._computeDropTarget(ev)?.pos_in ?? null` only if other callers still need the scalar; otherwise migrate them.

- [ ] **Step 3: Expose it on the imperative API** the parent binds (search where `_canvasApi.computeDropX` is set — the API object literal — and add `computeDropTarget: (ev) => this._computeDropTarget(ev)`).

- [ ] **Step 4: Update the move handler** (`_onMouseMove` ~387 and `_onMouseUp` ~412) to move along the item's own wall and persist `wall_side` + the right axis:

```javascript
        // _onMouseMove, moving branch:
        const tgt = this._computeDropTarget(e);
        if (!tgt) return;
        const item = this.T.movingItem;
        if (item.wall_side === "left") {
            if (item.z_position_in === tgt.pos_in) return;
            item.z_position_in = tgt.pos_in;
        } else {
            if (item.x_position_in === tgt.pos_in) return;
            item.x_position_in = tgt.pos_in;
        }
        this._buildScene(this.props);
```

```javascript
        // _onMouseUp, onMoveItem payload:
        this.props.onMoveItem({
            item,
            wall_side:     item.wall_side || "back",
            x_position_in: item.x_position_in,
            z_position_in: item.z_position_in,
            pinnable:      isPinnable(item.cabinet_type),
        });
```

- [ ] **Step 5: Verify** move still works on the back wall (regression) and a left-wall item slides along Z.

- [ ] **Step 6: Commit**

```bash
git commit -am "feat(3d): canvas wires nearest-wall drop target + left-wall move"
```

---

### Task 5: Mesh assembly — seat base/wall cabinets on the left wall via a Group frame

**Files:**
- Modify: `addons/southbrook_kitchen_3d_configurator/static/src/js/canvas/kitchen_canvas.esm.js` (the `_buildScene` item loop, ~250)
- (No change to `base_cabinet.esm.js` / `wall_cabinet.esm.js` internals — they keep building at `item.x_position_in`.)

**Interfaces:**
- Consumes: `item.wall_side`, `item.z_position_in`, `item.width_in`.
- Produces: left-wall base/wall cabinets rendered at X≈0, running along Z, depth into +X, door facing the room.

**Transform (worked out):** Build the cabinet at **local origin** by passing the builder a shallow-cloned item with `x_position_in = 0`. Reparent the returned meshes into a `THREE.Group`. Then per wall:
- **back:** `group.position.set(item.x_position_in * IN, 0, 0)`, `group.rotation.y = 0` — identical to today.
- **left:** `group.rotation.y = Math.PI / 2` (local +Z depth → world +X into room; door faces room), `group.position.set(0, 0, (item.z_position_in + item.width_in) * IN)` so the cabinet spans world Z ∈ `[z_position_in, z_position_in + width_in]` (local +X length maps to world −Z under +90°, so the group origin sits at the far edge).

- [ ] **Step 1: Add a group-wrapping helper** in `kitchen_canvas.esm.js`:

```javascript
    _placeCabinetGroup(THREE, scene, built, item) {
        const g = new THREE.Group();
        for (const m of built.objects) g.add(m);   // reparents from scene
        if (item.wall_side === "left") {
            g.rotation.y = Math.PI / 2;
            g.position.set(0, 0, ((item.z_position_in || 0) + (item.width_in || 0)) * IN);
        }
        // back wall: builder already baked x_position_in; leave at origin.
        scene.add(g);
        return g;
    }
```

Note: for **back-wall** items the builder still bakes `x_position_in`, so we do NOT clone-to-zero for them — only left-wall items are built at local origin. Branch accordingly (Step 2).

- [ ] **Step 2: Branch the item loop** (~250). For base + wall types, when `wall_side === 'left'`, build at local origin and wrap; otherwise keep the existing direct-push path:

```javascript
        const buildOnWall = (buildFn, it) => {
            if (it.wall_side === "left") {
                const localItem = { ...it, x_position_in: 0 };
                const built = buildFn(THREE, mk, P, localItem);
                const g = this._placeCabinetGroup(THREE, scene, built, it);
                this.T.cabObjs.push(g);
                if (built.clickable) this.T.clickable.push(...built.clickable);
            } else {
                push(buildFn(THREE, mk, P, it));   // existing back-wall path
            }
        };
        items.filter(it => it.cabinet_type === "base").forEach(it => buildOnWall(buildBaseCabinet, it));
        items.filter(it => it.cabinet_type === "wall").forEach(it => buildOnWall(buildWallCabinet, it));
        // tall/corner/filler/panel: unchanged (back-wall only for now)
```

Confirm `mk`/`makeMesh` adds meshes to `scene`; `group.add(m)` reparents them out of `scene` cleanly (THREE removes from prior parent on add). The dispose pass must also walk groups — verify `roomObjs`/`cabObjs` disposal handles a `THREE.Group` (traverse children) at the top of `_buildScene`; if it only disposes `.geometry`/`.material`, add a `group.traverse` guard.

- [ ] **Step 3: Verify** a left-wall base cabinet sits flush against the left wall, extends into the room, door facing in; a back-wall cabinet is visually unchanged (screenshot compare).

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(3d): render base/wall cabinets on the left wall (group frame)"
```

---

### Task 6: Parent — Auto/Back/Left toggle, add path, per-run layout packing, persistence

**Files:**
- Modify: `addons/southbrook_kitchen_3d_configurator/static/src/js/kitchen_configurator.js`
- Modify: `addons/southbrook_kitchen_3d_configurator/static/src/xml/kitchen_configurator.xml` (toolbar toggle; confirm exact template path)

**Interfaces:**
- Consumes: canvas `computeDropTarget(ev)`; `_recomputeLayoutFromItems` packer.
- Produces: `state.forcedWall` (`'auto'|'back'|'left'`) passed to `<KitchenCanvas forcedWall=...>`; new items carry `wall_side`; save payload includes `wall_side` per line.

- [ ] **Step 1: Toggle state** — add to `useState` (~48): `forcedWall: "auto"`. Add a handler:

```javascript
    _setForcedWall(mode) { this.state.forcedWall = mode; }
```

Pass to the canvas prop as `this.state.forcedWall === "auto" ? null : this.state.forcedWall` (compute in the template-bound getter or a small method — keep the ternary out of the OWL `t-` attribute per `[[owl_tokenizer_constraints]]`; expose `get canvasForcedWall()`).

- [ ] **Step 2: Toolbar UI** — in the configurator toolbar XML, add a 3-segment control:

```xml
<div class="btn-group sbk-wall-select" role="group" aria-label="Target wall">
    <button type="button" class="btn btn-sm"
            t-att-class="state.forcedWall === 'auto' ? 'btn-primary' : 'btn-outline-secondary'"
            t-on-click="() => this._setForcedWall('auto')">Auto</button>
    <button type="button" class="btn btn-sm"
            t-att-class="state.forcedWall === 'back' ? 'btn-primary' : 'btn-outline-secondary'"
            t-on-click="() => this._setForcedWall('back')">Back</button>
    <button type="button" class="btn btn-sm"
            t-att-class="state.forcedWall === 'left' ? 'btn-primary' : 'btn-outline-secondary'"
            t-on-click="() => this._setForcedWall('left')">Left</button>
</div>
```

- [ ] **Step 3: Add path** — `_onCanvasDrop` (~525) uses the new target; `_addCabinetFromProduct` accepts `wall_side` + `pos_in`:

```javascript
    _onCanvasDrop(ev) {
        ev.preventDefault();
        this.state.dragHover = false; this.state.draggedProduct = null;
        // ...resolve pid / product unchanged...
        const target = this._canvasApi?.computeDropTarget(ev) ?? null;
        // Out-of-scope types can't live on the left wall yet → force back.
        let wall = target ? target.wall_side : "back";
        const type = product.cabinet_type || "base";
        if (wall === "left" && !["base", "wall"].includes(type)) wall = "back";
        this._addCabinetFromProduct(product, target ? target.pos_in : null, wall);
    }
```

In `_addCabinetFromProduct(product, targetPos = null, wallSide = "back")` set `wall_side: wallSide` on `newItem`, and when `wallSide === "left"` store the drop coordinate in `z_position_in` (not `x_position_in`, which stays 0 for the hug), else keep existing X behaviour. Toast text should name the wall ("Added Base 24 on the left wall at 42″").

- [ ] **Step 4: Per-run layout packing** — in `_recomputeLayoutFromItems` (~752) split each row by `wall_side` and pack the left run along its own axis. `packRow` currently packs by `x_position_in`; add a `packRowZ` variant (or parametrize the axis key) that packs left-wall items by `z_position_in`:

```javascript
        const backBases = bases.filter(it => (it.wall_side || "back") !== "left");
        const leftBases = bases.filter(it => it.wall_side === "left");
        packRow(backBases);      // packs by x_position_in (unchanged)
        packRowAxis(leftBases, "z_position_in");   // packs by z
        // same split for walls; tall/corner stay back-only
```

Add `packRowAxis(row, axisKey)` mirroring `pack_row.esm.js` but reading/writing `axisKey`. Left-wall items must NOT be swept into the back-wall X cascade.

- [ ] **Step 5: Persistence** — the save/serialize path (search the payload built for `_queueAutoSave` / the write RPC, and the `onMoveItem` handler) must include `wall_side` and `z_position_in` on every line so the server design line stores them. Confirm the design.line write accepts `wall_side` (Task 1 field).

- [ ] **Step 6: Verify** end-to-end in the browser: toggle to Auto, drop near the left wall → cabinet lands on left wall, persists across reload; toggle to Back, drop near left wall → lands on back wall (forced); a second left-wall cabinet packs next to the first along Z, not overlapping.

- [ ] **Step 7: Commit**

```bash
git commit -am "feat(3d): wall selector toggle + left-wall add/layout/persist"
```

---

### Task 7: Reconcile — second (left) wall + wall_side routing

**Files:**
- Modify: `addons/southbrook_kitchen_3d_configurator/models/reconcile.py` (`_reconcile_one`, steps 3–4, ~188)
- Test: `addons/southbrook_kitchen_3d_configurator/tests/test_left_wall_reconcile.py`

**Interfaces:**
- Consumes: `design.room_depth_in`, `dline.wall_side`, `dline.z_position_in`.
- Produces: a second `southbrook.room.wall` ("Wall B", `wall_order=20`, `length_mm = room_depth`); each SO line routed to back/left wall with `position_from_left_mm` = X (back) or Z (left).

- [ ] **Step 1: Write the failing test**

```python
def test_reconcile_creates_left_wall_and_routes_lines(self):
    design = self._make_design(room_width_in=120, room_depth_in=96, partner=self.partner)
    self._add_line(design, cabinet_type="base", wall_side="back", x_position_in=12, z_position_in=0)
    self._add_line(design, cabinet_type="base", wall_side="left", x_position_in=0, z_position_in=24)
    self.env["southbrook.design.reconcile"].cron_reconcile_designs()
    room = design.room_id
    self.assertEqual(len(room.wall_ids), 2)
    back = room.wall_ids.filtered(lambda w: w.wall_order == 10)
    left = room.wall_ids.filtered(lambda w: w.wall_order == 20)
    self.assertAlmostEqual(left.length_mm, round(96 * 25.4))
    left_sol = design.sale_order_id.order_line.filtered(
        lambda l: l.wall_id == left)
    self.assertEqual(len(left_sol), 1)
    self.assertAlmostEqual(left_sol.position_from_left_mm, round(24 * 25.4))
```

- [ ] **Step 2: Run it, verify it fails** (only one wall today; left line lands on Wall A).

- [ ] **Step 3: Implement** — replace step 3 (single-wall) with back+left ensure, then route in step 4:

```python
        # 3) Ensure a back wall (Wall A, order 10) and a left wall (Wall B, order 20).
        Wall = self.env["southbrook.room.wall"]
        IN = IN_TO_MM
        back_len = int(round((design.room_width_in or 0) * IN))
        left_len = int(round((design.room_depth_in or 0) * IN))
        back_wall = room.wall_ids.filtered(lambda w: w.wall_order == 10)[:1]
        if not back_wall:
            back_wall = Wall.sudo().create({
                "room_id": room.id, "name": "Wall A", "length_mm": back_len,
                "wall_order": 10, "has_base_cabinets": True,
                "has_upper_cabinets": True, "has_tall_cabinets": True,
            })
        elif back_wall.length_mm != back_len:
            back_wall.sudo().length_mm = back_len
        left_wall = room.wall_ids.filtered(lambda w: w.wall_order == 20)[:1]
        if not left_wall:
            left_wall = Wall.sudo().create({
                "room_id": room.id, "name": "Wall B", "length_mm": left_len,
                "wall_order": 20, "has_base_cabinets": True,
                "has_upper_cabinets": True, "has_tall_cabinets": True,
            })
        elif left_wall.length_mm != left_len:
            left_wall.sudo().length_mm = left_len
```

Then in step 4, choose wall + axis per line:

```python
            on_left = dline.wall_side == "left"
            target_wall = left_wall if on_left else back_wall
            pos_in = (dline.z_position_in if on_left else dline.x_position_in) or 0
            line_vals = {
                # ...unchanged...
                "wall_id":               target_wall.id,
                "position_from_left_mm": int(round(pos_in * IN)),
                # sb_layout_x/z_mm keep the raw scene coords as today
            }
```

Note: the old fallback that reused `room.wall_ids[:1]` (unordered) MUST be removed — always match by `wall_order` so re-runs are idempotent (do not create a third wall).

- [ ] **Step 4: Run test, verify pass. Run the full module test suite — no regressions.**

- [ ] **Step 5: Commit**

```bash
git add addons/southbrook_kitchen_3d_configurator/models/reconcile.py \
        addons/southbrook_kitchen_3d_configurator/tests/test_left_wall_reconcile.py
git commit -m "feat(3d): reconcile creates left wall + routes lines by wall_side"
```

---

### Task 8: End-to-end smoke test + code review

**Files:** none (verification task)

- [ ] **Step 1:** Cold `-u` on a clone DB; open the 3D configurator on a real design.
- [ ] **Step 2:** With toggle on **Auto**, drag a base cabinet toward the left wall → it seats on the left wall, door into the room. Drag another → packs beside the first along Z.
- [ ] **Step 3:** Toggle **Back**, drop near the left wall → lands on back wall (forced). Toggle **Left**, drop a wall cabinet → seats on the upper-left run.
- [ ] **Step 4:** Reload the page → left-wall cabinets persist in place. Run the reconcile cron → `sale.order` shows Wall A + Wall B with correct `position_from_left_mm`.
- [ ] **Step 5:** Confirm a back-wall-only design from before this change renders pixel-identical (no regression).
- [ ] **Step 6:** Run `lint-owl-expr.py` + the module test suite green. Do a focused code review of the diff (per repo convention).

## Self-Review notes

- **Spec coverage:** all 6 original gaps mapped — wall_side field (T1), lanes (T2), raycaster (T3), canvas wiring + move (T4), mesh orientation (T5), toggle/add/layout/persist (T6), reconcile second wall (T7), verify (T8).
- **Out-of-scope, documented:** tall/corner/filler/panel on the left wall fall back to back-wall placement (T6 Step 3). Corner collision (base on each wall meeting at x≈0,z≈0) is intentionally deferred — matches current back-wall non-blocking behavior.
- **Type consistency:** `computeDropTarget` returns `{wall_side, pos_in}` everywhere; `wall_side` values are `'back'|'left'` in Python + JS; toggle state uses `'auto'|'back'|'left'` and maps `'auto'→null` at the canvas boundary.
- **Risk watch:** T5 group-reparent + dispose is the highest-risk change; verify the `_buildScene` dispose pass traverses groups. T7 must key walls by `wall_order` (not `[:1]`) to stay idempotent.
