# Configuration Engine Spec (G4)

> The brain of the SAMI / Southbrook AI Kitchen Platform. Given a
> confirmed room + appliance set + a theme + the available cabinet
> templates, the Configuration Engine produces a placement — every
> cabinet's position, dimensions, and adjacency — that a designer can
> hand to manufacturing without re-laying-out by hand.

**Status:** GREEN — gate closed 2026-06-09
**Module:** `southbrook_config_engine` (Module 7)
**Engine version key:** `southbrook.config_engine.v1`

---

## 1. Inputs

Every input is read from the workspace **only when**
`sb.kitchen.project.is_ready_for_config_engine()` returns True. That
gate enforces the GAP-02 human-confirmation contract — the engine never
acts on un-reviewed Gemini guesses.

```
1. The room geometry (from sb.kitchen.ai.analysis, confirmed)
   - wall_segments: ordered list (length_mm, has_windows[], has_doors[])
   - ceiling_height_mm
   - floor_area_m2

2. The appliance set (sb.kitchen.appliance records, each confirmed)
   - kind, position_x/y, width/height/depth, requires_clearance_mm
   - The wall_segment_id is reconstructed by snapping position_x/y to
     the closest segment

3. The theme (sb.kitchen.project.theme)
   - One of signature | elegance | contemporary | contractor
   - Drives which door style + box material defaults the engine prefers

4. The available cabinet templates
   - The 12 product.template records seeded by southbrook_estimating
   - Each carries a dimension envelope (width: enum of stops, min, max,
     default) per the in-repo CLAUDE.md §4.2

5. The hardware-resolution service
   - env['southbrook.hardware.catalog'].resolve() — invoked per cabinet
     after placement to attach SKU counts to each placed cabinet
```

---

## 2. Output

One **placement plan** that the workspace surfaces as the JSON stored
on `sb.kitchen.design.option.placement_data_json` for the option being
generated. Schema:

```jsonc
{
  "schema": "southbrook.config_engine.v1",
  "engine_version": "1.0",
  "project_id": 17,
  "design_option_id": 42,
  "theme": "signature",
  "ts": "2026-06-09T19:00:00Z",
  "runs": [
    {
      "id": "run_north",
      "wall_segment_id": "wall_north",
      "anchor_x_mm": 0,
      "anchor_y_mm": 0,
      "direction": "east",
      "length_mm": 4200,
      "cabinets": [
        { "seq": 1,  "template_xml_id": "southbrook_estimating.base_1dr",
          "width_mm": 300, "height_mm": 720, "depth_mm": 580,
          "x_offset_mm": 0,   "door_count": 1, "drawer_count": 0,
          "soft_close": true,
          "hardware_pick_summary": { "BLM-110-SC": 2, "MRH-HDL-PUL128": 1 } },
        { "seq": 2,  "template_xml_id": "southbrook_estimating.base_2dr",
          "width_mm": 800, "height_mm": 720, "depth_mm": 580,
          "x_offset_mm": 300, "door_count": 2 /* ... */ },
        { "seq": 99, "type": "filler",
          "width_mm": 42,  "x_offset_mm": 1100 }
      ],
      "appliance_slots": [
        { "appliance_id": 7, "x_offset_mm": 1142, "kind": "stove",
          "width_mm": 762, "clearance_mm": 30 }
      ]
    }
    /* ...one entry per wall segment that carries cabinets... */
  ],
  "warnings": [
    "Run 'run_east' has 12 mm leftover at the right end — absorbed by extending the right-most cabinet to 312 mm."
  ],
  "errors": []
}
```

If the engine cannot produce a valid plan (e.g. a wall is shorter than
the smallest cabinet + a required appliance), it returns an envelope
with `runs: []` and a populated `errors` list — never a partial plan.

---

## 3. The four classes of constraint

The engine resolves placement against four constraint classes. Order
matters — earlier classes are hard stops the engine never violates;
later classes are soft preferences the engine optimises against once
the hard constraints are satisfied.

| Class | Hard / soft | Example |
|---|---|---|
| C1 — Appliance clearances | hard | Stove needs `requires_clearance_mm` of empty space on each side; dishwasher must be flanked by base cabinets |
| C2 — Width fit | hard | Σ(cabinet widths + appliance widths + filler) = wall length within ±1 mm |
| C3 — Configurator rules (Rules 1–4 from Excel→Odoo Mapping §3.4) | hard | Series→door-style; box-material→series; width→door-count; family→soft-close |
| C4 — Theme preferences | soft | Signature theme prefers 800 mm 2-door base widths; Contractor theme prefers 600 mm 1-door simplicity |

C1+C2+C3 violations cause `errors`. C4 violations cause `warnings` only.

---

## 4. The placement algorithm

The engine is a constraint-solver in the Prodboard tradition (see
`docs/PRODBOARD_MANIFEST.md` §5 — recipe grammar — for the shape of
the input vocabulary). The core loop:

```
for each wall_segment:
    1. Identify appliance slots on this segment (sorted by position).
    2. Compute the contiguous cabinet stretches between slots
       (left-end-of-wall → first appliance, between adjacent appliances,
       last appliance → right-end-of-wall).
    3. For each stretch, run pack_stretch(stretch_length, theme).
    4. Reconcile: total span must match wall length within 1 mm; if
       leftover > 1 mm, distribute as filler at preferred locations
       (right-of-run preferred over center, per AYA cascade Rule F1).
    5. Resolve corner cabinets at L/U/island intersection points using
       the corner-solution rules in §5.

pack_stretch(L, theme):
    Greedy-then-balance:
    1. Pick the largest theme-preferred cabinet width that fits L.
    2. Subtract; recurse on (L - chosen_width).
    3. If the recursion would produce an unpaired narrow cabinet
       (< 225 mm), back-up one step and try the next-preferred width.
    4. If all greedy attempts fail to fit within ±1 mm, return the
       best partial + the leftover as filler width.
```

Cabinet widths are drawn from the DimensionEnvelope.items set per
template (see §1 input list). The engine NEVER invents widths outside
the envelope.

---

## 5. Corner solutions

L-shape and U-shape kitchens introduce corners. The engine picks among:

| Solution | When | Width contribution |
|---|---|---|
| Blind corner | Either corner; cheapest | 900 mm; gives up ~600 mm of the perpendicular run |
| Lazy Susan | Either corner; medium price | 900 mm each side, full access |
| Diagonal corner | Either; premium themes only | 900 mm each side, 45° face |
| 45° filler | Tight runs that can't fit a 900 mm corner | Variable; access compromised |

The choice is recorded as a `template_xml_id` on the corner cabinet
record in the output plan. Themes drive the preference:

- Signature → lazy susan first, diagonal second
- Elegance → diagonal first, lazy susan second
- Contemporary → blind corner first, lazy susan second
- Contractor → blind corner only

---

## 6. Appliance clearance rules

Per-kind clearance contracts (mm of cabinet-or-filler-or-empty space
required around the appliance):

| Kind | Left | Right | Above (counter clearance) | Top reservation |
|---|---|---|---|---|
| stove | 30 | 30 | 700 (hood clearance) | hood/microwave allowed |
| oven_wall | 0 (in column) | 0 (in column) | N/A | tall column required |
| fridge | 25 (counter-depth) | 25 | full-height column | none |
| dishwasher | 0 (cabinet-flank) | 0 (cabinet-flank) | 0 | none |
| sink | 0 (cabinet-flank) | 0 (cabinet-flank) | 0 | window allowed |
| microwave | 0 (when wall-mounted) | 0 | N/A | shelf above |
| hood | N/A | N/A | 700 above stove | none |

If an appliance's `requires_clearance_mm` (Module 5 field) exceeds these
defaults, the override wins. Per-kind defaults are stored as
`sb.placement.rule` records so the rules table is data, not code (per
init-doc anti-pattern list).

---

## 7. The rules table (`sb.placement.rule`)

Every preference + constraint above lives as a record so they're
auditable and rev-able without a code change.

| Field | Type | Notes |
|---|---|---|
| name | Char | Human label, e.g. "Signature prefers 800mm 2-door base" |
| kind | Selection | `clearance` \| `width_pref` \| `corner_pref` \| `filler_rule` |
| theme | Selection (nullable) | Restricts rule to one theme |
| appliance_kind | Selection (nullable) | Restricts to one appliance kind |
| constraint_json | Text | Type-specific payload |
| priority | Integer | Tie-breaker when multiple rules of the same kind apply |
| active | Bool | Allow rev cycling without delete |

Loading on engine init: every active rule sorted by priority, indexed by
(kind, theme, appliance_kind) for fast lookup during placement.

---

## 8. Test layouts (the gate criteria for shipping Module 7)

The Module-7 test suite must exercise all five canonical layouts. Each
test seeds a project + appliances + a theme + a target wall geometry
and asserts the produced placement plan obeys C1–C3 hard constraints.

```
Galley:    two parallel runs, no corners.
L-shape:   two runs joined by one corner.
U-shape:   three runs joined by two corners.
Island:    one wall run + a free-standing island block; the island has
           cabinets back-to-back (door on both faces).
Peninsula: one wall run + a perpendicular peninsula attached at one end.
```

Plus targeted unit tests:

- Filler width arithmetic — random wall lengths from 1800 mm to 6000 mm
  pack within ±1 mm 100% of the time.
- Clearance enforcement — stove placed so that an adjacent dishwasher
  violates the 30 mm rule is rejected with a clear `errors[]` entry.
- Corner solution selection — Signature theme produces a lazy-susan
  cabinet at an L-corner; Contractor produces a blind corner.
- Rule precedence — when a clearance rule and a width preference
  conflict, the clearance rule wins (hard > soft).

---

## 9. Idempotency + re-runs

Re-running the engine on the same inputs produces a byte-identical
output. Module 7 implements this by:

- Sorting all inputs deterministically (appliances by position_x then
  position_y then id; rules by priority then id).
- Tie-breaking placement choices by a deterministic hash of the input
  payload (not random).
- Never reading the wall clock during placement — `ts` in the output
  is the one exception, stamped only after placement completes.

This matters because an ECO that changes a single cabinet template
shouldn't reshuffle the entire kitchen — only the cabinets whose
template was rev'd. The byte-identical guarantee makes ECO impact
analysis tractable.

---

## 10. What the engine intentionally does NOT decide

- **Substrate / colour / finish** — these are configurator attributes
  the customer picks per cabinet after placement. The engine
  produces template + dimension placements; the configurator picks
  variant attributes inside that.
- **Hardware quantities** — the engine emits a `hardware_pick_summary`
  per cabinet by calling Module 3's resolution service, but it does
  NOT consolidate hardware totals across the kitchen. That's the
  workspace's job at quote-generation time.
- **Pricing** — engine outputs template + dims; the pricelist module
  decides cost.
- **CAD geometry** — the engine emits dimensions; FreeCAD renders
  geometry from them.

---

## 11. Versioning rule

Any change to the output JSON schema bumps `engine_version` in the
output. Consumers (the workspace UI, Module 8 customer portal preview,
Module 4 production-package generator) MUST accept the new version AND
continue accepting v1.0 for one Phase cycle.
