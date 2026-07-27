# Prebuilt Sample Kitchen Templates + Parametric Entry — Design Spec

**Date:** 2026-07-27
**Status:** Approved direction (user: "build it using your recommendations"). Catalog table populated from the blindspot/ReAct validation run (wf_b7ad9cf6).
**Module:** `southbrook_kitchen_3d_configurator` (Odoo 19 CE, LIVE) + template data. Inputs: user brief (browser audit), codebase gap investigation (`ktmpl-investigation.md`), catalog/parametrics workflow (`ktmpl-catalog-design.md`).

## Goal
A customer/rep starts from a **prebuilt sample kitchen** instead of an empty room: pick a **shape** (thumbnail dropdown), a **cabinet count**, a **module width** (24″ default), and **appliance sizes** (stove/fridge/dishwasher) — the layout generates live in the 3D canvas with real positions, engine-derived corners/fillers, and a price; then they only reorient/swap boxes.

**Why (user-stated value):** the point is pre-made templates that bake in the parts that are *difficult to quote and build from scratch* — above all **corner units**. Templates assist the 3D configurator by handing the corner engine a known-good arrangement, so the outcome is **Fast, Easy and Correct for both the user and the system** (correct geometry AND a quotable, manufacturable BoM feeding the live weight/procurement chain).

**Priority order:** corner-bearing templates (L-shape, then U) are the flagship deliverable; single-wall/galley are the on-ramp/regression baseline. Honest catalog constraint: exactly ONE corner SKU exists today (SB-CORNER, LH-only, inconsistent data) — corner templates ship correct within that limit, with visible placeholders where corner variants (RH, blind, lazy-susan) are missing; the corner-SKU data repair (out of scope here) is the unlock for full corner coverage.

## Locked decisions
1. **Slots, not SKU pins** — template lines reference archetype/role slots; a resolver maps slot→product at instantiation (optional `product_id` hard-pin supported for fixed quotable BOMs later).
2. **10 ft reference runs** on the starter set; templates are data (`noupdate="0"`) so dimensions are correctable without deploys.
3. **Finish-agnostic templates** — resolver takes series/finish arguments.
4. **Four-dropdown entry UX** (user-specified): shape (with small top-view thumbnail) → number of cabinets → cabinet module size → appliance sizes; every change regenerates the preview live; conflicts constrain the dropdown or flag — never silently grow the room. **Placement + ordering (user directives 2026-07-27): TOP FRAME, ordered — room dimensions first, then Kitchen Shape (Straight/L/U/H…), then the cabinet selections (count/size/appliances); shape options and count bounds constrain to what fits the entered room** — inline and always visible, not a separate modal; the transient picker remains only as the backend/menu entry path.

## Architecture (reuse-first — grounded in the gap investigation)
- **Instantiation = data + existing engine.** `southbrook.kitchen.template.action_instantiate(...)` creates *canonical* `southbrook.kitchen.design.line` records (product/slot, wall, run_seq, widths) and then calls the existing **`action_auto_arrange`** pipeline (`resolve_and_layout` / `anchor_pose_mm`, kitchen_layout_engine) to derive every x/y/z/rotation. **Zero new geometry code.**
- **Corners:** template places a corner *slot* only; the live corner engine (rules-as-data, per-leg claims) does the geometry. Templates never pin corner dims/hand.
- **Fillers:** NOT templated. The engine's rule-driven filler derivation (M3, fillers as derived BOM lines) computes them per instantiation/reflow. The brief's "write filler lines explicitly" is superseded.
- **Appliances:** design lines (`zone='accessory'`, dedicated `cabinet_type` handling, `position_label` e.g. "APPLIANCE: range 36″"), with widths from dropdown #4 and clearances enforced via the existing `clearance_front_mm` placement-rule support. `sb.kitchen.appliance` is NOT used (drags in workspace/crm; wrong coordinate model).
- **Room shape lexicon:** reuse `southbrook.room._LAYOUT_SHAPES` — no parallel enum.
- **Picker:** the existing `kitchen.design.template.picker` transient is rewired: `preset` selection → `template_id` M2One (+ the four parametric fields); old preset values map to new template codes (compat); its stale pre-multiwall coordinates die with the migration to template data. Confirm → instantiate → open the design in the configurator. Toolbar "Start from Template" button added in the canvas UI.
- **Naming:** layout flip is `action_flip_layout` (NOT "mirror" — collides with the manufacturing reconcile mirror).

## Data model
`southbrook.kitchen.template`: name, code (unique), description, `layout_shape` (reuse room lexicon), default_room_width/depth/height_in, default module_width_in, min/max cabinet counts per run, default_filler_strategy, default_wall_cab_top_alignment, thumbnail (binary; generated top-view SVG at first), sequence, active, notes.
`southbrook.kitchen.template.line` (slot): template_id, slot_code, cabinet_type [base|wall|tall|corner|appliance], zone, wall, run_seq, sequence, nominal_width_in (0 = takes module width), archetype_id (preferred), product_id (optional pin), is_appliance_slot, appliance_type [range|fridge|dishwasher|hood|…], priority (drop order when the room shrinks), notes.

## Resolver contract
`resolve(slot, *, series, finish, door_style, width_in, hand) -> product.product | None`.
On failure: create the line as a **visible placeholder** (`position_label = "UNRESOLVED: …"`, flagged on a design-level validation list). Never silently substitute wrong geometry; never drop the slot.

## Parametric fill math (dropdowns #2–#4)
Per run: `usable = wall_len − corner_claims − Σ appliance_widths`; `n_max = floor(usable / module_width)`; count dropdown is bounded to `[min, n_max]` live. Remainder → engine filler rules. If a change makes `count × width + appliances > usable`: the UI constrains (greys invalid counts) and, at instantiation, validation blocks with a clear message — the room is never silently grown (a known live defect: 54→60→84″ growth; fixed as part of this).

## Manipulation API (server actions; thin JS calls)
`design.action_flip_layout(axis)`, `design.action_rotate_layout(quarters)`, `line.action_swap_product(product_id)`, `line.action_set_width(width_in)`, `line.action_move(wall, run_seq)`, `design.action_reflow()` — each re-runs auto-arrange + recomputes `estimated_price`, `total_cabinets`, `base_count`, `wall_count`, `remainder_in` from `cabinet_line_ids` (single source of truth). Note: swap/set-width exist client-side today; these formalize them server-side (poses always re-derived, so cheap).

## Counts fix (isolated task — cross-consumer change)
`total_cabinets` currently counts fillers. Change: fillers excluded, `filler_count` added; audit the consumers (header UI, reports) in the same task.

## Canvas/JS scope (narrowed by ground truth)
- REAL: `window.__sbk.getLayout()` (authoritative `[{id, sku, wall, x_position_in, width_in, cabinet_type, is_filler}]` for tests/automation); undo (or at minimum no auto-save before first user action); ghost preview on wall hover (glow/label already exist).
- ALREADY FIXED (skip): "+ Add" no-op, ✕ remove button (2026-07-27 defect sweep F14/F15). NOT REPRODUCIBLE (skip unless seen): drag mis-grab (uses dataTransfer JSON).
- Known split-brain to fix here: room-resize regen still calls the naive single-wall `/layout` generator instead of the corner engine — route it through auto-arrange.

## Template catalog (validated ≥7/10 by the ReAct pass — 47 blindspots, 16 candidates, 6 kept; full detail in `ktmpl-catalog-design.md`)

| Code | Shape | Room (in) | Core slots | Key knobs | Buildable today | Score |
|---|---|---|---|---|---|---|
| SW-08 | straight | 96×60 | SB30+range30, 1 base module, fillers, 1×W24 | module_width | placeholder-appl | 8 |
| SW-12 | straight | 144×72 | T24 pantry + SB30+range36 + 2 modules, 2×W24 | module_width, tall_count 0–2, range 30/36 | **Yes** | 8 |
| GAL-08 | galley | 96×90 | sink/range wall + fridge/prep wall, 42″ NKBA aisle floor | aisle_width, module_width | placeholder-appl | 7.5 |
| GAL-10 | galley | 120×96 | as GAL-08 + T24; per-wall fills | module_width (linked/per-wall), aisle=48 | placeholder-appl | 8 |
| PEN-10x10 | peninsula | 120×120 | back run + peninsula (dw24 + SB-WORKTOP eat-bar) | peninsula_length 42–72, module_width | **Yes** | 9 |
| H-14x12 | custom/H | 168×144 | 4 independent segments + 2 connector gaps | run_length per segment, gap_width 6–36 | placeholder-appl; needs per-segment x (stopgap) | 7 |
| **L-10x8** | l_shape | 120×96 | **the flagship** — back+left runs meeting at the corner slot (engine-claimed both legs) | module_width, per-wall run lengths | **gated on the corner-SKU repair below** | — |

**Parametric core (one formula, reused everywhere):** `fixed_width_sum → remaining → base_module_count = floor(remaining / module_width) → leftover → fillers (FP3, ceil(leftover/3))`; knobs per the catalog doc §2.1 incl. `module_width_in` becoming a REAL user knob (today it's read-only derived — a code-vs-brief mismatch fixed in T2), `aisle_width_in` (NKBA 42″ floor), `peninsula_length_in`, per-segment `run_length_in`/`gap_width_in`.

## Corner-SKU repair — PULLED INTO SCOPE (user directive: corners are the point)
The validation kept zero L/U templates solely because of the corner SKU data gap (SB-CORNER: LH-only; dims inconsistent 33″-vs-36″-vs-24″-depth; carousel description vs highline archetype). The corner ENGINE is sound. In-scope data repair (southbrook_estimating data, no geometry import): (1) fix SB-CORNER's dimension consistency to its archetype (CC-CHL); (2) add the RH variant; (3) then ship **L-10x8** as the flagship corner template. U-shape (2 corners) remains next-release, gated on blind/lazy-susan SKUs (still out of scope).

## Out of scope
Corner SKU creation/repair; Prodboard geometry import; archetype backfill on the 9 unlinked products (templates degrade to visible placeholders until that data lands). Option-A-style consumption changes. `sb.kitchen.appliance` integration.

## Acceptance criteria
- Picker: four dropdowns as specified; changing any regenerates the canvas live; invalid combinations are constrained/flagged; confirm opens a draft design.
- Each shipped template instantiates → renders via auto-arrange with no further computation; corners/fillers engine-derived; `total_cabinets` = non-filler cabinet lines.
- Flip/rotate/swap/set-width/move/reflow round-trip with price+counts consistent (asserted via `__sbk.getLayout()` where UI-visible).
- Undersized room ⇒ blocking validation (or priority-based slot drop), never silent room growth.
- Unresolved slots visible as placeholders, never silently dropped/substituted.
- Tests: per-template instantiation + manipulation round-trips; JS layout assertions via `getLayout()`.

## Delivery note (2026-07-27)

Shipped on branch `feat/kitchen-templates` (all tasks INLINE after the
session's subagent cap):

| Task | Version | Commit | What shipped |
|---|---|---|---|
| T1 | 5.28.0 | 9ceac65 | template + slot models (slots-not-pins, room lexicon reuse) |
| T2 | 5.28.0 | 4dab395 | resolver, parametric_fit, action_instantiate, appliance stand-ins + placement rules, unresolved honesty |
| T3 | 5.28.0 | 4fbd6c5 | four-dropdown picker, top-frame button, generated SVG thumbnails, compat preset map |
| T4 | 5.29.0 | 9bb9e79 | starter catalog data (4 active + 2 inactive), PER-WALL fit math, variant-bearing resolver filter, legacy 5.6.12 fallback restored |
| T5 | 5.30.0 | 39e558d | flip/rotate/reflow + swap/width/move (canonical-only, savepoint-atomic, engine-rederived poses) |
| T4a | 5.31.0 + estimating 9.1.0 | f8a36bf | SB-CORNER repair (33"→36", RH twin SB-CORNER-R, SB-WALL-CORNER seeded), hand-aware corner variant pick, L-10X8 flagship |
| T6 | 5.32.0 | 21d677d | total_cabinets excludes fillers; filler_count; migration recompute; consumer audit |
| T7 | 5.33.0 | 589c307 | __sbk.getLayout, autosave first-action gate, /rearrange engine-routed resize, ghost preview, no silent room growth |
| T8 | — | (this commit) | README, delivery note, plan tick |

**Reconciled compat-preset → code map:** empty → (legacy blank-canvas
dims, 5.6.12 contract preserved); galley → GAL-10; l_shape → L-10X8;
u_shape → U-10X8X10 (NOT shipped — blocked on 2-corner inventory;
falls back to the legacy preset seeding until it exists).

**Shipped inactive (honest placeholders):** PEN-10X10 (engine lacks
free-anchor peninsula runs — the peninsula segment is deliberately not
authored); H-14X12 (engine supports one run per wall; needs
run_length_in/gap_width_in knobs — catalog blocker #7).

**Deviations / discoveries:**
- Widths retargeted to the VARIANT-BEARING demo catalog (SB30 30" sink,
  B24/DB24 24", T24, W24): the canonical Q8 templates are OCA
  config_ok with zero variants and cannot back a slot. The resolver
  now filters on `product_variant_ids` (both rungs).
- parametric_fit went per-wall (galley is two independent runs) and
  gained corner leg claims + lead absorption; also fixed a latent
  multi-repeat-slot clone bug in the T2 math.
- The corner engine SUBSTITUTES run-lead cabinets fully inside its
  cell; L-10X8 is authored with explicit corner-buffer leads
  (LEAD-B/LEAD-L, W1/W2) so the promised kitchen survives.
- The engine "fits" impossible changes by ARCHIVING lines, not
  raising — every mutation surface (T5 actions, T7 /rearrange) adds a
  post-arrange honesty guard.
- T3's picker UserError on unloaded compat codes had silently broken
  two track_b 5.6.12 pins — restored via a legacy-preset fallback
  (T4); the l_shape pin itself is now SUPERSEDED by the shipped
  L-10X8 template and was updated with citation (T4a).
- action_move writes `sequence` alongside `run_seq` (the engine's
  auto-assign path orders by flat input order on all-back designs).
- T7's engine-resize gate is `designId AND hydrated` (brief said
  designId only): rearranging a lineless template draft would wipe the
  generated preview.
- Version renumbering vs the plan: T4a took 5.31.0, pushing T6→5.32.0
  and T7→5.33.0.

**Cut/deferred (with reason):** undo/redo (investigation E-f — the
autosave gate is the safe half); island/peninsula free-anchor ORM
support (engine capability, not data); U/G-shape templates (2-corner
inventory + wall-corner variants); drag mis-grab (non-reproducible in
this session); linked-vs-independent per-wall module width knob and
run_length_in/gap_width_in (needed only by the inactive H-14X12);
SB-WALL-CORNER placeholder price ($295) flagged for the shop to
reprice.
