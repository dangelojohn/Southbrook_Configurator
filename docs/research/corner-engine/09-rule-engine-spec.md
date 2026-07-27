# 09 — Corner Cabinetry Rule Engine Specification
### Phases 8 + 9 synthesis: from research corpus → implementable rule engine for `kitchen_layout_engine` + Odoo

*Authored 2026-07-27. Synthesizes the 221 machine-readable entries in docs 01–08
against the CURRENT Southbrook codebase (southbrook_estimating
19.0.7.18.0 `kitchen_layout_engine.py`, southbrook_kitchen_3d_configurator
19.0.5.20.0). Every architecture choice cites a research decision id
(`07-cad-math-architecture.md`) or rule id from the corpus.*

---

## 0 · Where we are vs. where this goes

The engine today (post-2026-07-26 L-shape fix) already has, in embryonic form,
most of what the commercial systems model:

| Commercial concept (research) | Today in `kitchen_layout_engine` | Gap |
|---|---|---|
| Wall segments with local frames (`wall-segment-local-frames`) | `_WALL_SPEC` — 4 fixed orthogonal walls, along-axis + rotation per wall | walls are room-derived, not first-class; no non-90° headings |
| Corner junction as a real object (`corner-junction-as-real-object`) | `_CORNER_SPECS` + `detect_corners()` + inserted corner *node* | junction exists only transiently inside `resolve_and_layout`; not persisted, not typed |
| Rules as data (`rules-as-external-data-not-engine-code`) | `_CORNER_RESOLVE`, `_CORNER_FOOTPRINT_MM`, `_CORNER_SKU` are **hardcoded tables** | move to per-product placement rules (this spec, §3–§4) |
| Solid vs. swept envelope separation (`swept-envelope-separate-from-solid-geometry`) | solid AABB only (`footprint_mm` / `footprint_from_anchor_mm`) | no door-swing / mechanism / clearance envelopes |
| Filler as packing slack (`filler-as-packing-slack-variable`) | fillers are server-`/layout` artifacts on the back wall only | corner fillers (`filler-blind-corner-min`, 3″ rule) not modeled |
| AABB broad + OBB narrow phase (`aabb-broadphase-obb-sat-narrowphase`) | AABB only — sufficient while rotations ∈ {0,90,180,270} | needed the day 135° walls land |

The evolution path the original module docstring promised — *"runs come from an
adjacency graph… only `_resolve_runs()` changes"* — is exactly what the research
corpus validates (Cabinet Vision walls→assemblies object tree; Chief Architect
corner objects). This spec makes that concrete.

---

## 1 · Deliverable 1 — Taxonomy (normative index)

The taxonomy is **data**, not prose: the 18 base types
(`01-base-corner-taxonomy.md` JSON) + 11 wall types (`02-…`) are the canonical
`corner_type` registry. Southbrook's live SKUs map onto it today:

| Live SKU (prod DB) | taxonomy `type_id` | Notes |
|---|---|---|
| `SB-CORNER` (36×24×34.5, the auto-insert base) | `diagonal-corner-lazy-susan` | generic susan-capable; 36″ legs both walls |
| `SB-CORNER-BLIND` | `blind-corner-basic` | needs blind-pull + 3″ filler rules (§4) |
| `SB-CORNER-DIAG` | `diagonal-corner-lazy-susan` | |
| `SB-CORNER-LSUSAN` | `pie-cut-bifold-susan` | |
| `SB-WALL-CORNER` (30×12×30, auto-insert upper) | `pie-cut-wall-corner` / `diagonal-wall-corner` | pick one; today it renders as a square cell |
| `SB-CM-MC` | hardware `kessebohmer-lemans-ii` family | mechanism, not a cabinet — attaches via BOM |
| `SB-CM-BCO`, `SB-CM-PBCO`, `SB-CM-PSOC`, … | hardware entries in `04-hardware-envelopes.md` | Vauth-Sagel family |

**Data gap found while mapping (fix in data, not code):** the `SB-CORNER-BLIND
/ -DIAG / -LSUSAN` templates carry `southbrook_cabinet_type = NULL`,
`southbrook_is_cabinet` unset, and 24×24 dims — they're invisible to the 3D
catalog and would lay out square. The 33″-named variant vs. template
`southbrook_width_in=36` mismatch is the same class (see F1/F17 report).

---

## 2 · Deliverable 3 — Formal placement model

### 2.1 Wall graph (replaces the implicit 4-wall room)

```
Room
 └── walls: ordered list of WallSegment
       WallSegment { id, origin_mm (x,z), heading_deg, length_mm }
 └── junctions: derived — consecutive segment pairs
       Junction { id, wall_a, wall_b, interior_angle_deg,
                  corner_point_mm, type: inside|outside }
```

- Orthogonal rooms: the current `_WALL_SPEC` **is** this graph specialized to
  headings {0, 90, 180, 270} — byte-compat is preserved by generating today's
  four segments from `room{width,depth}`.
- `interior_angle_deg ≈ 90 ± tol` → standard corner rules; `135` → the
  `angle-corner-45-135` type family (research: no standard SKU table exists —
  the engine must refuse to auto-resolve and demand explicit selection).
- Rotation stays single-axis Y (`single-axis-rotation-only-at-orthogonal-headings`)
  but `rotation_deg` becomes `wall.heading_deg` (+180 for facing) rather than a
  member of a fixed enum — the persisted-anchor conversion (`anchor_pose_mm`)
  already generalizes since it keys off rotation.

### 2.2 Cabinet anchoring

Three anchor classes (research: Cabinet Vision 9-parameter placement,
Chief Architect corner objects):

1. **run-anchored** — `(wall_segment_id, run_seq, tier)` → along-wall cursor
   packing (today's model, unchanged).
2. **junction-anchored** — `(junction_id, tier)` → the cabinet *consumes*
   `wall_a_consumed` + `wall_b_consumed` from BOTH adjacent segments and offsets
   both runs (today's `wall_start_offsets`, generalized: consumption per leg
   comes from the type's rule record, not `_CORNER_FOOTPRINT_MM`).
   Blind corners are ASYMMETRIC: `wall_a_consumed=45″(box+pull+filler),
   wall_b_consumed=24″(depth)` — the current square-cell model cannot express
   this; the per-leg pair can (`diagonal-corner-two-leg-parameterization`,
   `blind-corner-as-clearance-problem-not-solid`).
3. **free-anchored** — islands/peninsulas: explicit pose, no cursor (today's
   `__pose` mechanism, kept).

`tier ∈ {base, wall, tall}` replaces `_layer_of()`'s cabinet_type sniffing;
tall spans both tiers for collision purposes.

### 2.3 Placement pipeline (formal)

```
resolve(design):
 1  G   ← wall_graph(room)
 2  A   ← assign(cabinets → run|junction|free anchors)        # user intent or auto_assign
 3  for each inside junction j, tier t:
 4      if both incident runs occupied at t:
 5          type ← select_corner_type(j, t, rules, leg_space)  # §4.3
 6          insert junction-anchored corner node(type)
 7          reserve leg consumption on both segments (per-leg, per-tier)
 8          displace/park colliding run members (archive, never delete)
 9  P   ← pack runs (cursor per (segment, tier), start = junction reservations)
10  F   ← insert fillers where rule engine demands (corner fillers first,
          then scribe fillers at run ends)                     # §4.4
11  V   ← validate envelopes (solid → hard; motion → hard; clearance → soft)  # §5
12  emit placements (centre-pose) → anchor_pose_mm at ORM boundary
```

Steps 1–9 exist today in specialized form; 10–11 are new; the loop
structure is `resolve_and_layout` with `_CORNER_RESOLVE` replaced by rule
lookups. **`select_corner_type` is the only new decision procedure** — today it
is the constant `_CORNER_SKU[layer]`.

---

## 3 · Deliverable 7 — The rule record (Phase 8 schema)

One record per *placeable product* (template or variant — §6). The engine
consumes it as a plain dict; nothing in the pure module reads Odoo.

```json
{
  "rule_id": "sb-corner-diag-susan-36",
  "product_default_code": "SB-CORNER",
  "corner_type_id": "diagonal-corner-lazy-susan",
  "anchor_class": "junction",
  "tier": "base",

  "wall_consumption_in": { "wall_a": 36.0, "wall_b": 36.0 },
  "box_in": { "width": 36.0, "depth": 36.0, "height": 34.5 },
  "required_wall_length_in": { "wall_a_min": 60.0, "wall_b_min": 60.0 },

  "fillers_in": { "wall_a": 0.0, "wall_b": 0.0,
                  "note": "diagonal susan needs none; blind types carry 3.0 per filler-blind-corner-min" },

  "envelopes": {
    "solid":     { "kind": "aabb_local", "x": [0, 36], "z": [0, 36] },
    "door_swing":{ "kind": "arc", "hinge": "bifold-45", "radius_in": 16.5,
                   "arc_deg": [0, 170], "ref": "blum-corner-bifold-hinge-60" },
    "mechanism": { "kind": "cylinder", "radius_in": 14.0, "ref": "revashelf-lazy-susan-series" },
    "clearance": { "kind": "aabb_local", "z": [36, 54], "severity": "soft",
                   "why": "nkba access in front of corner (nkba-work-aisle-min-single-cook)" }
  },

  "neighbors": {
    "permitted":  ["base-run", "filler", "sink-base"],
    "forbidden":  [{ "type": "dishwasher", "within_in": 2.0, "ref": "dishwasher-corner-clearance" },
                   { "type": "tall",       "side": "hinge",  "ref": "corner-door-vs-tall-pantry" }],
    "min_adjacent_cabinet_in": 9.0,
    "handle_rule": "corner-door-vs-drawer-handle"
  },

  "install": { "order_priority": 0, "ref": "install-corner-first",
               "site_adjustable_in": 1.0, "site_ref": "susan-corner-undersize-clip" },

  "transform": { "origin": "junction-corner-point", "reference_edge": "wall_a",
                 "anchor_edge": "back-left-bottom" },

  "manufacturing": { "deck_shape": "pentagon", "route": "nest-cnc",
                     "ref": "nesting-preferred-for-irregular-parts" },

  "sources": ["01-base-corner-taxonomy.md#diagonal-corner-lazy-susan"],
  "confidence": "verified"
}
```

Field semantics (Phase 8 checklist → schema):

| Phase 8 requirement | Schema field |
|---|---|
| Cabinet Type | `corner_type_id` |
| Required Wall Length | `required_wall_length_in` (box + fillers + min neighbor) |
| Required Fillers | `fillers_in` |
| Collision / Door Swing / Drawer / Hardware envelopes | `envelopes.{solid,door_swing,mechanism}` |
| Min/Max Adjacent, Permitted/Forbidden Neighbors | `neighbors` |
| Installation Order | `install.order_priority` (0 = set first) |
| Manufacturing Rules | `manufacturing` (+ BOM/routing in Odoo, §6) |
| Placement/Corner Priority | `install.order_priority` + `anchor_class` |
| Bounding/Clearance Geometry | `envelopes` |
| Transform Origin / Reference Edge / Anchor Edge | `transform` |
| Connection Rules | `neighbors.permitted` + junction membership |

### 4.3 `select_corner_type(junction, tier, rules, leg_space)`

Deterministic filter-then-rank (no solver needed at this scale —
`rules-as-external-data-not-engine-code`):

1. **Filter**: rules with `anchor_class=junction`, matching `tier`, whose
   `required_wall_length_in` fits `leg_space` on both legs, whose forbidden
   neighbors aren't present, and (135° junctions) whose type supports the angle.
2. **Rank**: explicit product priority (an Odoo sequence field) → storage
   volume → cost tier. Ties → the design-level default
   (`design.corner_preference`).
3. **None fit** → emit `CORNER_UNRESOLVED` diagnostic naming the failed
   predicate per candidate ("blind corner needs 45″ on wall A, 41″ available")
   — never silently skip; this replaces today's warning-only SKU-missing path.

### 4.4 Filler insertion (Deliverable 4 partial)

- Corner fillers: from the selected rule's `fillers_in` — a real design line
  (`cabinet_type=filler`, junction-anchored) so it reaches BOM/cutlist, per
  `blind-corner-filler-strip-separate-bom-line`.
- Run-end scribe fillers: pack remainder < min-cabinet-width → filler at the
  run's HIGH end (out-of-square absorption goes to the corner-remote end,
  `absorb-out-of-square-at-shorter-leg-end`).
- Width floors: 1.5″ door-only / 3″ drawer-or-handle-adjacent
  (`filler-corner-generic-rule`, `scribe-filler-*`).

---

## 5 · Deliverable 4 — Collision & clearance engine

Three envelope classes, evaluated in the validator AND (hard ones) at placement:

| Class | Geometry | Violation | Today's hook |
|---|---|---|---|
| `solid` | AABB (OBB when non-orthogonal lands) | **blocking** | check #7 `FOOTPRINT_COLLISION` — keep, feed from rule envelopes instead of box dims |
| `motion` (door arcs, LeMans sweep, Magic-Corner extraction, wall-oven door drop) | arc/box swept regions from `04-hardware-envelopes.md` numbers | **blocking** vs. solids of others; motion-vs-motion = warning | new check #10 |
| `clearance` (NKBA landings, aisles, appliance service) | soft boxes from `03-standards` + `06-collision-matrix` | **warning** with rule citation | new check #11 |

Broad phase: same-tier AABB sweep (already how check #7 iterates). Narrow
phase for arcs: sample the arc's chord box — exactness is unnecessary at
kitchen tolerances (`clearance-as-continuous-area-penalty`).
The 23 `06-collision-matrix.md` pairs are the acceptance-test matrix: each
`pair_id` becomes one regression test with its documented clearance number.

---

## 6 · Deliverable 7 — Phase 9 Odoo data model

**Principle: rules live on products; the engine stays pure.** (Mirrors
Cabinet Vision UCS-on-products and Microvellum formula-driven products.)

New model in `southbrook_estimating` (not the 3D module — manufacturing owns it):

```
southbrook.placement.rule
  product_tmpl_id     m2o product.template (required, 1:1-ish)
  corner_type_id      selection ← taxonomy registry (data file)
  anchor_class        selection run|junction|free
  tier                selection base|wall|tall
  sequence            integer (corner-selection priority, §4.3)
  payload             Json  — the §3 record, validated on write against a
                      jsonschema kept in the module (single source of truth)
  active              boolean
```

- **Why one Json payload + a few indexed columns** rather than 30 columns: the
  envelope grammar will grow (arcs, cylinders, swept boxes); schema-validated
  JSON keeps migrations cheap while `corner_type_id/tier/sequence` stay
  queryable. Same trade Microvellum makes (spreadsheet formulas as payload).
- Loader: `sale.order`/design model serializes active rules →
  `engine.resolve(..., rules=[payload,...])`. The pure module gains ONE new
  input and zero Odoo knowledge.
- Seed data: `data/placement_rules.xml` instantiating §3 records for the 5 live
  corner SKUs + standard bases/walls, numbers from docs 01–04 (each with
  `sources`).
- Variants: attribute-driven differences that change placement (hinging L/R,
  33″ vs 36″) must either (a) resolve per-variant via `product_id` override
  records, or (b) be excluded from attributes and modeled as separate
  templates. **Recommendation: (b) for width (the 33″ corner variant is the
  live data bug), (a) for handedness.**
- BOM/routing (Phase 9 tail): mechanism SKUs (`SB-CM-*`) are BOM components of
  the corner cabinet template (`microvellum-bom-quantity-formula-driven`
  pattern → Odoo: BOM lines with attribute-conditional `bom_line.attribute_value_ids`);
  routing = `saw/nest → edgeband → drill → assemble → pack` workcenters
  (`standard-routing-station-sequence`), with the corner deck flagged
  `nest-cnc` (`nesting-preferred-for-irregular-parts`).
- Installation metadata: `install.order_priority` prints on the shop
  copy/labels (corner = #1, per `install-corner-first`) —
  `part-barcode-per-station-tracking` pattern.

---

## 7 · Migration path (incremental, each step shippable)

| Step | Change | Files | Risk |
|---|---|---|---|
| M1 | `southbrook.placement.rule` model + jsonschema + seed data for 5 corner SKUs; engine accepts optional `rules` param; `_CORNER_SKU`/`_CORNER_FOOTPRINT_MM` become the fallback when no rule matches | southbrook_estimating (model+data), engine (one kwarg) | low |
| M2 | Per-leg consumption + asymmetric corners (blind!) — junction reservation uses `wall_consumption_in` per leg; `select_corner_type` replaces constant SKU | engine `resolve_and_layout`, kitchen_design `_CORNER_SKU` removal | medium |
| M3 | Corner fillers as design lines + BOM | engine (filler nodes), reconcile | medium |
| M4 | Envelope validator checks #10/#11 + the 23-pair regression matrix | kitchen_design validator, tests | low |
| M5 | Wall graph (`WallSegment`/`Junction` objects) generated from room; `_resolve_runs` keyed by segment id — behavior-identical for rectangles | engine | medium |
| M6 | Non-90° junctions: refuse-auto + manual placement; OBB narrow phase | engine | high |

M1+M2 alone convert today's "always insert a 36×36 square" into
"insert the right corner cabinet for the space, or say why not" — the
biggest single UX gain available.

---

## 8 · Verification obligations

- Every numeric consumed from docs 01–08 keeps its `confidence` tag; rules
  built on `estimate` entries must render their warning in the UI
  ("clearance estimated — verify on site").
- KCMA A161.1 numbers are triangulated (primary PDF unparseable) — **human
  verification against the purchased standard required** before any becomes a
  hard gate (flag from doc 03).
- Golden tests: back-wall parity (exists) + L/U/G corner suites (exist) +
  per-`pair_id` collision matrix (new) + one asymmetric blind-corner fixture
  (new — nothing covers asymmetric consumption today).
