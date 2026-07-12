# Architecture Review — Southbrook Kitchen Configurator (Odoo 19 CE)

**Date:** 2026-07-12 · **Method:** ownership/leak review (Prompt 1) + complete `wall`-field
lifecycle trace (Prompt 4). Analysis only — no code. Every `file:line` below was read
directly this session; claims that were *not* executed are labeled **Reasoned**.

Scope note: the review prompts said "Odoo 16"; this codebase is **Odoo 19 CE**. Reviewed
as-is.

---

## 1. Canonical ownership — intended vs. actual

| Responsibility | Intended owner | Actual owners found | Verdict |
|---|---|---|---|
| **Rendering** | `KitchenCanvas` + `canvas/*` builders, governed by `COORDINATE_CONTRACT` | (1) `KitchenCanvas` (backend configurator + website design tab) · (2) `southbrook_customer_portal/static/src/js/kitchen_canvas.js` — a separate 227-line THREE scene rendering the Configuration Engine's geometry JSON · (3) `southbrook_estimating_website/…/sample_3d_widget.esm.js` — homepage demo scene | **Leaking.** Three independent renderers; only (1) is under the coordinate contract + golden-scene harness. |
| **Layout** (where cabinets go) | `southbrook_estimating/models/kitchen_layout_engine.py` (pure, deterministic) | (1) the engine · (2) `southbrook_kitchen_3d_configurator/controllers/main.py:47-246` — `/layout`'s own generative fill with inline cursor math (`:164-190`) · (3) client-side `packRow` / `_recomputeLayoutFromItems` (`kitchen_configurator.js` + `canvas/pack_row.esm.js`) — X-axis-only packing | **Leaking.** Three implementations of placement; only the engine is wall-aware and corner-aware. |
| **Persistence** | `southbrook.kitchen.design(.line)` as canonical model; `reconcile.py` mirrors to `sale.order.line` | Two write APIs with **different field coverage**: backend `save_design` (full-replace, `main.py:284,394-413`) vs. website `design-3d/add`/`move` (per-line). Plus `save_position`. | **Leaking.** Same model, two writers, inconsistent fields (see §3). |
| **Interaction** | `KitchenCanvas` (pointer, raycast, hover, drop lanes, handles, wall pick) | `KitchenCanvas` owns the mechanics (confirmed by PR1: `kitchen_canvas.esm.js:85-86,324,447,542-549,648`). Consumers own app-level add/drop/toast flows; website adds a touch fallback. | **Healthy** (post-PR1). App-level duplication is acceptable; mechanics are not duplicated. |

**A boundary that is *correct* and worth protecting:** the engine tags corner nodes
semantically (`corner_cabinet`, `layer`, `handed`) and the Odoo layer maps them to SKUs
(`kitchen_design._CORNER_SKU`). Product identity stays out of the pure engine. Keep it
that way.

---

## 2. The load-bearing violation: the backend editor never reads the canonical model

**Reasoned from code (not yet executed live):**

- On open, `kitchen_configurator.js:156-166` → `_refreshLayout()` → **`/layout`**, whose
  inputs are room dimensions + partner + filler strategy only (`main.py:47-49`) — **no
  `design_id`, no saved lines**. Its response **replaces** `state.items` wholesale
  (`kitchen_configurator.js:359`).
- The endpoint built to rehydrate saved lines — `load_design_lines`
  (`main.py:454-487`, self-described: *"so the client can rehydrate a saved manual
  placement instead of throwing it away"*) — has **zero client call sites**.

So the backend surface **writes** the canonical model (`save_design`, `save_position`)
but **never reads it back**. In compiler terms: the editor saves the AST, then on reopen
*recompiles from defaults* instead of loading it. Every downstream symptom — walls lost,
pins depending on a side-channel, the demo-fill appearing over saved work — descends from
this one inversion. The website surface does **not** have this violation: it hydrates from
`_southbrook_design_payload` (`main.py:2464`), i.e. from the canonical lines.

---

## 3. `wall` lifecycle (Prompt 4)

Field: `southbrook.kitchen.design.line.wall` — `Selection([back,left,right,front])`,
`default="back"` (`kitchen_design.py:1723-1726`).

### Writers
| # | Writer | Status |
|---|---|---|
| W1 | Model default (`"back"`) | ✔ |
| W2 | Website add: `design-3d/add` → `line_wall` (`main.py:2841-2853`) | ✔ writes user's pick |
| W3 | Auto-arrange: engine result → `dl.write({"wall": …})` (`kitchen_design.py:541`) | ✔ |
| W4 | Backend `save_design` `line_vals` (`main.py:394-413`) | ✘ **drops it** — every full save of an existing design resets nothing *only because* it never writes the key; a PR2 write must be added here |

### Readers
`kitchen_design.py:498` (cabs builder, `dl.wall or "back"`) → engine
`_resolve_runs`/`_place_on_wall`/`detect_corners`; website `same_wall`/`run_seq`
computation (`main.py:2842-2851`). The backend client and canvas read **nothing** (until
PR2+).

### Serialization boundaries — where `wall` lives or dies
| # | Boundary | File:line | Verdict |
|---|---|---|---|
| B1 | Backend save: client item → `line_vals` | `main.py:394-413` | **LOST** (key absent) |
| B2 | `/layout` response → `state.items` | `main.py:47-246` → `kitchen_configurator.js:359` | **N/A — regenerated**; every item implicitly back-wall |
| B3 | `load_design_lines` line → JSON | `main.py:470-487` | **LOST** (key absent) — and the endpoint is dead client-side |
| B4 | Website payload line → JSON | `_southbrook_design_payload`, `main.py:2464-2500` | **LOST semantically.** Pose (x/z/rotation) survives so it *renders* correctly, but `wall`/`run_seq` are not emitted — client-side items lose their wall identity after reload. Latent, not live, because wall-dependent computations re-read the DB server-side. |
| B5 | Website move: `design-3d/move` writes | `main.py:2518-2556` | **NOT UPDATABLE** — x/y/z/rotation only; a cross-wall drag (PR4) cannot re-home a cabinet |
| B6 | Manufacturing mirror: `reconcile.py` | `:191-199,220` — `room.wall_ids[:1]`, single "Wall A", `wall_order 10` | **FLATTENED** — every design line maps to one wall regardless of `dl.wall` |
| B7 | Engine round-trip (`cabs` → placements → `dl.write`) | `kitchen_design.py:498,541` | **PRESERVED** ✔ |

### Sequence (current, backend surface)
```
KitchenCanvas ──(PR1: onWallSelect)──► activeWall          [UI state only]
   add cabinet ──► newItem {x,y,z…}                        [no wall — W4 gap]
   auto-save ──► save_design ──► line_vals                 [B1: wall LOST]
        ORM ──► DB (wall = default "back")
reopen ──► /layout (room dims only) ──► regenerated items  [B2: canonical model unread]
        └── load_design_lines: never called                [B3: dead + lossy]
reconcile cron ──► sale.order.line.wall_id = Wall A        [B6: flattened]
```

---

## 4. Hidden coupling that will fight future layouts (L/U/G, islands, peninsulas)

1. **Client packing is single-axis.** `packRow` sorts/packs by `x_position_in` only —
   structurally coupled to the back wall. PR4 must not extend it; it should *retire* in
   favor of engine placements (the engine already models runs per wall and anticipates
   an adjacency graph — its own header says walls become "just one constraint type").
2. **`/layout` conflates two concepts:** "suggest a demo fill for an empty room" and
   "refresh the editor's state." Splitting *suggest* from *echo state* is a precondition
   for PR2.5's restore path being clean.
3. **Dual coordinate convention in the renderer:** back-wall (rot 0) cabinets take the
   legacy absolute-X path; rotated cabinets take the group-transform path
   (`kitchen_canvas.esm.js:447,472`). PR3's unification — gated by the Prompt-3
   contract matrix — removes the special case islands/peninsulas would trip on.
4. **`wall` as a Selection will not survive islands.** An island cabinet has no wall.
   Don't widen the enum ad-hoc; when islands arrive, the anchor concept generalizes
   (engine's adjacency-graph note). Until then: one `WALLS` constant, one server-side
   validation point, so the future change is single-site.
5. **Three renderers** (§1) will drift visually on any new layout topology; only one has
   a golden harness. Consolidation is housekeeping, not urgent — but islands will make
   the drift visible to customers.

---

## 5. Smallest PR sequence that eliminates the leaks (no user-visible behavior change until PR4)

| PR | Content | Leak closed |
|---|---|---|
| **PR2** | `wall` at the backend write boundary: `WALLS` frozen constant (new code only), item→`line_vals` carry, server-side validation (reject non-members), NULL→`back` on read. TransactionCase: save/invalid/default. | B1, W4 |
| **PR2.5 (P1 — data-integrity defect, VERIFIED)** | **Restore-from-canonical:** when `designId` is present, hydrate from `load_design_lines` instead of `/layout`; `/layout` remains the empty-room suggest path. Emit `wall` (+`run_seq`) in **both** read serializers — ideally extract one shared line-serializer used by `load_design_lines` and `_southbrook_design_payload`. | §2 (the root violation), B3, B4 |
| **PR3** | Renderer coordinate-model unification. **Gate:** the Prompt-3 matrix (Component × uses X/Y/Z/rotation × contract violation) produced first, as a punch list. | coupling #3 |
| **PR3a** | Hoot infra + tests covering PR1–PR3 contracts (as previously scoped). | — |
| **PR4** | Wall-aware placement: delegate to the engine; retire client `packRow` for non-back items; add `wall` to `design-3d/move`. | coupling #1, B5 |
| **PR5** | U-shape. | — |
| **Backlog** (each its own PR, not now) | **B6 — reconcile multi-wall mirror. The manufacturing mirror assumes a single wall and is therefore not yet semantically correct for multi-wall kitchens** (every design line lands on "Wall A" regardless of `dl.wall`). Do not fix now; do not lose track — it becomes a manufacturing-correctness defect the day the first L-kitchen ships. Also: split `/layout` suggest-vs-echo (#2); renderer consolidation (#5); unify the two write APIs. | B6, #2, #5 |

**Ordering argument:** PR2.5 was originally "reload restores wall" inside PR2. The trace
shows reload restores *nothing* on this surface — a pre-existing gap bigger than walls.
Splitting keeps PR2 verifiable server-side (TransactionCase, isolated clone) and gives the
restore repair its own review, where the risk actually lives.

---

## 5a. Canonical boot contract (normative as of PR2.5)

The backend configurator's boot sequence is a **contract**, not an implementation detail.
Any change to it is an architectural change and must be reviewed as one.

```
NEW design (no design_id):            EXISTING design (design_id present):
  products                              products
  user_defaults                         user_defaults
  /layout   (generator seeds items)     load_design_lines  (canonical lines seed items)
                                        render — /layout MUST NOT run, on boot or at any
                                        later point in the session (the generator has no
                                        knowledge of saved state and save_design is a
                                        full-replace writer: regenerate-then-save is the
                                        destructive-overwrite path PR2.5 closed)
```

Edge case: a `design_id` whose design has **zero saved configurator lines** boots via the
NEW-design path (generator), and stays on it until the first real save.

## 5b. Architectural note — the `extractProps` params gap (systemic, not wall-specific)

Root cause verified against the vendored Odoo 19 web source (`action_service.js`):
client-action components receive `props = {action, actionId, …}`; **`action.params` is
only flattened onto props when the client action defines `extractProps`** — this
component never did, so **every** value `action_open_configurator` passed
(`design_id`, `room_width_in/depth/height`, `partner_id`, `filler_strategy`,
`soffit_height_in`, `wall_cab_top_alignment`) silently arrived as `undefined` and fell
back to defaults. Consequences went well beyond walls: saved room dimensions ignored,
the D3 partner→channel-pricelist forwarding dead (always retail), filler/soffit/
alignment presets ignored. PR2.5 fixed the intake (`props.action.params` with flat-prop
fallback). **Standing rule:** any Odoo 19 client action in this codebase that consumes
`params` must read them from `props.action.params` (or define `extractProps`) — audit
this whenever a client action "mysteriously uses defaults."

## 6. Verification ledger

- **Verified (read at cited lines, this session):** every `file:line` in §§1–4.
- **VERIFIED 2026-07-12 (browser + DB forensic check on design 81):** reopening a saved
  backend design does NOT load the canonical model. Opening design 81 (DB truth: 84×24
  room, 3 base cabinets at x=0/24/48) via its "Open 3D Configurator" button rendered a
  **12-inch empty default room with 0 cabinets**; the network capture showed exactly
  `products` + `user_defaults` + `layout` — **`load_design_lines` never fired**. Worse
  than regeneration: the saved room dimensions aren't even passed. **PR2.5 is hereby a
  P1 data-integrity defect** — the editor is not faithfully reopening its own canonical
  model, and `save_design`'s full-replace semantics mean any post-open mutation
  auto-saves the regenerated state over the saved design (destructive overwrite).
  Design 81's lines were confirmed untouched after the read-only inspection
  (5 rows, write_date unchanged).
- **Not examined:** `southbrook_customer_portal/kitchen_canvas.js` beyond its header;
  FreeCAD-bridge geometry parity; `sample_3d_widget` internals. None are on the PR2–PR5
  path.
