# Corner Resolution — Geometric Rule (Left-Wall "Vanishing Cabinet" Fix) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make adding a cabinet to any wall (esp. the left) always show that cabinet on that wall; auto-insert a corner cabinet only when two runs *geometrically meet* at the shared corner cell — and when it does, render it correctly in the corner with a visible transition. Fixes the reported "cabinets can't be added to the left wall" (they were silently consumed by eager, mistagged corner resolution).

**Architecture:** Three coordinated fixes in the pure engine + the add controller + the 3D-tab UI. (1) `detect_corners` becomes geometric (corner-cell footprint occupancy, not mere wall occupancy). (2) The inserted corner node carries the correct `wall`/`rotation_deg` so left/front corners render *in the corner*, not flat on the back wall. (3) The add endpoint never resolves a corner on the add that first introduces a wall's run — the first cabinet on a new wall is always placed & returned visibly; resolution happens on later adds / explicit auto-arrange. Plus a fade+toast UX.

**Tech Stack:** Odoo 19 CE Python (pure engine `addons/southbrook_estimating/models/kitchen_layout_engine.py`, controller `addons/southbrook_estimating_website/controllers/main.py`), OWL (`addons/southbrook_estimating_website/static/src/js/design_tab.esm.js`).

## Global Constraints

- Odoo **19.0 CE** only. Pure engine stays pure/deterministic (no `Date.now`, no ORM inside `kitchen_layout_engine.py`).
- **Preserve back-wall parity:** a straight (back-only) kitchen must produce byte-identical placements. There is a golden back-wall parity test (`tests/test_layout_engine.py`) — it must stay green.
- Coordinate model (engine docstring): +X along back wall (0→width), +Z from back (0) toward front (0→depth), +Y up; `rotation_deg` right-handed about +Y; a cabinet at `rotation_deg=0` faces out of the back wall. Per-wall rotations already used elsewhere: back=0, front=180, left=90, right=270 (`_WALL_SPEC`).
- Corner cell = the `corner_size_mm` (914mm/36") square at a room corner. `footprints_overlap(a,b,eps)` (AABB overlap) and `within_room` already exist in the engine — reuse them, don't reinvent.
- Existing helpers to reuse: `_WALL_SPEC`, `_CORNER_SPECS`, `_layer_of`, `_place_on_wall`, `layout()` (which already honors an explicit `__pose` — cabinets with `__pose` skip run-packing), `_run_end`.
- OWL expressions obey `lint-owl-expr.py` (no Python `or`/`and`/`not`, no JS regex literals in `t-*`).
- End with a reproduction test + smoke test + code review.

---

### Task 1: Geometric corner detection

**Files:**
- Modify: `addons/southbrook_estimating/models/kitchen_layout_engine.py` (`detect_corners` ~294; and `resolve_and_layout` ~404 to place-then-detect)
- Test: `addons/southbrook_estimating/tests/test_layout_engine.py`

**Interfaces:**
- Consumes: `layout()`, `footprints_overlap`, `_CORNER_SPECS`, `_layer_of`, `_place_on_wall`.
- Produces: `detect_corners(cabinets, room, placements=None)` — a corner is active for a layer only when BOTH adjacent walls have a cabinet of that layer whose PLACED footprint overlaps that corner's `corner_size_mm` cell. Same return shape as today (list of `{corner, layer, walls, position_mm}`).

- [ ] **Step 1: Write failing tests**

Add to `test_layout_engine.py`:
- `test_corner_detected_only_when_footprints_reach_corner_cell`: back run with a cabinet occupying the back-left cell + left run with a cabinet occupying the back-left cell → `back-left` corner detected. A left cabinet placed FAR from the corner (z near room depth, not overlapping the cell) with a back cabinet at the corner → `back-left` NOT detected.
- `test_back_only_kitchen_detects_no_corner` (parity guard): all cabinets on back → `detect_corners` returns `[]`.

- [ ] **Step 2: Run tests, verify they fail.**

- [ ] **Step 3: Implement**

Restructure so detection uses real footprints:
- In `resolve_and_layout`, compute a provisional `placements = layout(assigned, room, **layout_kwargs)` FIRST, then call `detect_corners(assigned, room, placements=placements)`.
- In `detect_corners`, when `placements` is given, for each `_CORNER_SPECS` corner build the corner-cell AABB (`corner_size_mm` square anchored at that corner's `(x_key,z_key)`), and activate the corner for a layer only if BOTH walls have a cabinet of that layer whose placement AABB `footprints_overlap` the cell. Fall back to the current occupancy test only when `placements is None` (keeps any legacy callers working) — but `resolve_and_layout` always passes placements.
- Corner-cell AABB helper: derive `(x0,x1,z0,z1)` from `coord[xk]/coord[zk]` ± `corner_size_mm` toward room interior.

- [ ] **Step 4: Run tests, verify pass. Run whole engine suite — parity test still green.**

- [ ] **Step 5: Commit** `feat(layout): geometric corner detection (corner-cell footprint occupancy)`

---

### Task 2: Correct the inserted corner node's wall + orientation

**Files:**
- Modify: `addons/southbrook_estimating/models/kitchen_layout_engine.py` (corner-node construction ~492–508, the `_CORNER_RESOLVE` branch)
- Test: `addons/southbrook_estimating/tests/test_layout_engine.py`

**Interfaces:**
- Produces: each inserted corner node carries a `wall` + `rotation_deg` (or an explicit `__pose`) that renders it IN the corner, not flat on the back wall. `host_wall` remains solely the run whose cursor the corner joins — decoupled from the emitted `wall`.

- [ ] **Step 1: Write failing test**

`test_corner_node_tagged_and_oriented_for_its_corner`: an L formed by back + left runs meeting at back-left → the inserted corner node's `wall` is NOT plain `"back"` and its placement/rotation puts its footprint inside the back-left corner cell (assert via `footprints_overlap` with the cell and the rotation is a corner-appropriate value, not 0). Mirror for back-right (already correct — guards against regression) and front-left.

- [ ] **Step 2: Run test, verify fail** (today `wall=host_wall="back"`, rotation 0).

- [ ] **Step 3: Implement**

Give the corner node an explicit `__pose` centered in the corner cell (so `layout()` places it exactly there regardless of `host_wall` cursor), with a corner-appropriate `rotation_deg`, and tag `wall` with the corner's own identity (e.g. the corner name's primary side, or add `corner_walls=[wall_a,wall_b]`). Keep `host_wall`/`run_seq=-1` only for cursor bookkeeping of the adjoining run flow. Persisted `node["wall"]` (consumed at `kitchen_design.py:576` and `reconcile`) must be a valid selection value (`back/left/right/front`) — pick the side whose run the corner visually continues, or extend the model selection if a dedicated corner value is wanted (keep additive if so).

- [ ] **Step 4: Run tests, verify pass; full engine suite green.**

- [ ] **Step 5: Commit** `fix(layout): corner node renders in the corner (correct wall+rotation), not flat on back`

---

### Task 3: First cabinet on a new wall is never consumed on add

**Files:**
- Modify: `addons/southbrook_estimating_website/controllers/main.py` (`southbrook_api_design_3d_add` ~2836–2890)
- Test: `addons/southbrook_estimating_website/tests/` (add or extend a controller/integration test)

**Interfaces:**
- Consumes: `design.cabinet_line_ids`, `action_auto_arrange(sync=False)`.
- Produces: the add response ALWAYS includes the just-added cabinet on its wall; `action_auto_arrange` (corner resolution) runs only when the cabinet's wall ALREADY had ≥1 configurator cabinet BEFORE this add.

- [ ] **Step 1: Write failing test**

`test_first_cabinet_on_new_wall_is_returned_not_consumed`: seed a design with ≥1 back cabinet; POST add with `wall="left"`. Assert the response returns the new left line (its `wall=="left"`, present in `design.cabinet_line_ids`, active), and NO corner node was inserted (no `layout_role=="derived"` corner tagged away from left). Second test: with a left cabinet already present, adding a second left cabinet MAY trigger resolution (assert the relaid path is reachable).

- [ ] **Step 2: Run test, verify fail** (today the first left add triggers auto-arrange and the line is consumed).

- [ ] **Step 3: Implement**

Before creating the line, compute `wall_had_cabinets = bool(same_wall)` (the `same_wall` recordset already computed at ~2842 for `run_seq`). After placing the new line, gate the corner resolution: run the `walls_used>=2` → `action_auto_arrange(sync=False)` block ONLY when `wall_had_cabinets` is True. When it's the first cabinet on this wall, skip resolution and return the new item normally (so the client shows it on the wall). Keep the existing `_sb_place_line_on_wall` call so the cabinet still snaps onto its wall.

- [ ] **Step 4: Run tests, verify pass.**

- [ ] **Step 5: Commit** `fix(3d-add): never consume the first cabinet on a new wall; defer corner resolution`

---

### Task 4: Visible corner transition (fade + toast)

**Files:**
- Modify: `addons/southbrook_estimating_website/static/src/js/design_tab.esm.js` (the add-response handler ~987–992 `res.relaid` branch; and a small CSS/anim hook)
- Modify: `addons/southbrook_estimating_website/static/src/scss/design_tab.scss` (fade keyframes) if needed
- Test: manual visual (no OWL render harness for THREE here)

**Interfaces:**
- Consumes: the add RPC response `{relaid:true, payload}` (already returned when a corner is resolved).

- [ ] **Step 1:** When the add response has `relaid` (a corner was inserted), before swapping `state.items`, show a toast `"Corner cabinet inserted automatically."` (reuse `_pushToast(..., "success")`). Keep the existing scene swap.

- [ ] **Step 2:** Add a lightweight fade-in on newly-appeared corner items (gate on a flag in the payload item, e.g. `cabinet_type==="corner"` newly present) — a CSS class toggle / opacity tween on the canvas overlay, or a brief scene highlight. Respect `prefers-reduced-motion` (skip animation, keep the toast). Keep it minimal; do not block the render.

- [ ] **Step 3: Commit** `feat(3d-ux): toast + fade when a corner cabinet is auto-inserted`

---

### Task 5: Reproduction + smoke test + review

- [ ] **Step 1:** Cold `-u southbrook_estimating,southbrook_estimating_website,southbrook_kitchen_3d_configurator` on a clone DB (see `[[southbrook_v19cr_local_test_recipe]]`).
- [ ] **Step 2:** In the 3D Design tab: build a back run. Pick **Left**. Add one cabinet → **it appears on the left wall and stays** (the bug's direct repro — previously vanished). Verify via `save`/reload it persists with `wall="left"`.
- [ ] **Step 3:** Keep adding left cabinets toward the corner → when the runs meet at the corner cell, a corner cabinet appears **in the corner** (correct orientation) with the toast. No cabinet silently vanishes.
- [ ] **Step 4:** Repeat for **Right** and **Front** (regression — they must still work). Confirm a back-only kitchen is unchanged (parity).
- [ ] **Step 5:** Engine suite + `lint-owl-expr.py` green. Focused code review of the branch diff.

## Self-Review notes

- **Root cause coverage:** geometric detection (T1) stops the eager occupancy trigger; corner-node tag/orientation (T2) fixes the flat-on-back render; add-gating (T3) guarantees the first cabinet on a wall is always shown; UX (T4) makes any later corner replacement visible. T5 reproduces the exact user report.
- **Parity risk:** T1/T2 must not change back-only layouts — the golden parity test is the guard; keep the `placements is None` fallback so no other caller shifts.
- **Model value risk (T2):** `node["wall"]` is persisted to a Selection field `[back,left,right,front]` and mirrored to reconcile — must remain a valid value; if a dedicated corner concept is introduced, keep the schema change additive.
- **Type consistency:** `detect_corners` gains an optional `placements=None` kwarg; all in-repo callers updated to pass placements from `resolve_and_layout`.
