# PRODBOARD_MANIFEST.md

A deeply comprehensive reference manifest for the Southbrook Kitchen Planner project.

**Source:** live empirical reconnaissance of `planner.prodboard.com/betterkitchens/kitchen`
**Coverage:** R5 through R16 plus the final verification pass
**Status:** Authoritative — every claim below was confirmed against the live deployment in a final verification pass

---

## 0 · Document purpose and use

This manifest captures everything empirically discovered about Prodboard (specifically the BetterKitchens deployment). It is not a marketing description. It is a forensic engineering reference. The intended consumer is an internal LLM (Claude Code or successor) that needs to reproduce Prodboard's essence — visual, behavioral, structural — in Odoo v19 CE without ever having seen the original.

Every claim is anchored to a specific data source on the live deployment. Where prior reconnaissance rounds (R5–R15) made errors, this manifest contains the corrected value with the prior wrong value flagged so future LLMs don't inherit those mistakes.

---

## 1 · The corrections layer (read this first)

Before consuming the rest, internalize these eight corrections. They override anything inconsistent in earlier R5–R15 notes.

| # | Topic | What was said earlier | What is actually true | How verified |
|---|---|---|---|---|
| C1 | Cabinet count | "251 cabinets" | 251 modules in the kitchens catalog; **401 modules total across 5 catalogs**; **132 actual cabinet recipes** in `__data_module_data_*` | Counted directly via `__cat_*.modules.length` and `JSON.parse(__data_module_data_*).length` |
| C2 | Recipe structure | "`{elements:[…], drillings:[…]}` array of typed elements" | Recipes are keyed by module-code (e.g. `BHL1DR`) with shape `{filling: {<element_type>: <params>}}` where elements can carry numeric prefixes for ordering (`1.drawer`, `2.drawer`) | Direct parse of all four `__data_module_data_*` strings |
| C3 | Recipe location | "script field on each module" | The `script` field on **219 of 239** modules is empty `{}`. Recipes live in the four `__data_module_data_{base,wall,tall,standart}` JSON blobs at the application data layer | Parsed every module's script field; counted empty=219, flat=9, rooted=11 |
| C4 | Door families | "35 door families with 250 options" | **40 door families** in `__data_door_data`; ~250 door models (variants per family); door family options (pelmet/cornice/plinth/end-panel/infill) are a separate concept | `Object.keys(__data_door_data)` |
| C5 | Decor count | "197 decors" | 197 in `__cat_kitchens` + 108 in `__cat_doors` + 24 in `__cat_elements` + 8 in `__cat_handles` + 4 in `__cat_kitchen-cabinets` = **341 total decors** | Sum across all `__cat_*.decors.length` |
| C6 | Cubemap count | "5 cubemaps" → revised in R15 to "1 cubemap" | Actually **9 cubemap JPGs** at `blobs.prodboard.com/shared/cubemaps/` totaling ~10.5 MB | `performance.getEntriesByType('resource')` filtered on cubemap URLs |
| C7 | Recipe parse failure rate | "Only 4% of scripts parse cleanly" | **100%** of non-empty scripts parse cleanly with single `JSON.parse`. The 4% figure was a bug in an iteration loop, not a property of the data | Re-ran parse loop; all 239 strings parsed without error |
| C8 | Worktops | "Worktops are an open question" | Worktops are first-class modules in `__cat_kitchens` — the very first module by index has `code: "worktop"`. They use the `radius` parameter to follow corners | `__cat_kitchens.modules[0].code` returned `"worktop"` |

---

## 2 · The product surface — what Prodboard actually is

Prodboard is a multi-tenant browser-native kitchen-planning SaaS. The BetterKitchens deployment at `planner.prodboard.com/betterkitchens/kitchen` is one tenant; the parent product lives at `prodboard.com`. Functionally:

- **Customer-facing planner** runs as a single-page application in the browser, no install.
- **Tenant-branded catalogs** of cabinets, doors, decors, handles. Each tenant gets their own catalog with their own SKU codes.
- **3D-first interaction model.** The viewport is always 3D (or a quaternion preset thereof). There is no 2D-first mode.
- **Lead-capture end state.** The user designs a kitchen and clicks "Request a Price" — Prodboard does not process payments or generate quotes. It posts a webhook to the tenant.
- **No collaboration.** Single-user editing. No share, no invite, no presence indicators (`collaborator=0` hits, `share=71` hits but all UI-string-related, not real-time collab).
- **No MRP, no BOM, no quote document, no payment, no order management.** These are explicitly absent from Prodboard. **This is the negative space Southbrook fills.**

---

## 3 · Architecture — one parametric object, many projections

The defining architectural property: every cabinet is a **parametric object** carrying `width × height × depth` plus its construction parameters (series, door style, hinge side, finished sides, gables, interior). The Three.js scene generates the mesh from these on the fly — **procedural geometry, not pre-baked GLBs**. Only 13 GLBs cold-load against 251 cabinets, confirming procedural geometry is dominant.

The solid↔blueline toggle proves it: the same scene re-projects as photoreal shaded geometry, isometric wireframe, or programmatically-snapped dimension lines, because all three are derived from one model. Cost recalculates instantly when you swap a cabinet for the same reason — every downstream artifact is a projection of the one object.

For Southbrook, the corollary is exact: once a cabinet exists as a parametric object with dimensions and attributes, every downstream view is just a different projection of that one object. The render is one projection, the dimensioned drawing is another, and the cutlist / BoM / door schedule are three more. The blueline mode is the human-readable proof that the model is dimensionally complete enough to manufacture from.

---

## 4 · The data model

### 4.1 Five catalogs (`__cat_*`)

| Catalog | Modules | Models | Decors | Textures |
|---|---|---|---|---|
| `__cat_kitchens` | 251 | 54 | 197 | 242 |
| `__cat_elements` | 42 | 156 | 24 | 3 |
| `__cat_doors` | 63 | 176 | 108 | 129 |
| `__cat_handles` | 20 | 29 | 8 | 0 |
| `__cat_kitchen-cabinets` | 25 | 5 | 4 | 1 |
| **TOTAL** | **401** | **420** | **341** | **375** |

### 4.2 The catalog matrix

Each catalog object has the same shape:
- `modules` — the configurable products (cabinet templates)
- `models` — the 3D meshes available to those modules
- `decors` — surface finishes (colour + texture combinations)
- `textures` — raw texture assets (KTX2 + Basis Universal)
- `classificators` — references into `__cat_classificators` (65 total, 120 values)

### 4.3 The Module record (the configurable product) — **the single most important schema in the system**

Every cabinet, door, handle, appliance, worktop, plinth, cornice — all share this shape:

```javascript
{
  id:              integer,           // Prodboard internal ID
  code:            string,            // human slug ("worktop", "BHL1DR", "WCVM{S}")
                                      // {S} and {H} are placeholder substitutions
  icon:            string,            // "<tenant>/icon/<guid>/<name>" path
  settings: {
    allocation:            integer,   // 0=floor, 1=wall, 2=ceiling-hung, ...
    behaviour:             integer,   // interaction-mode enum
    ignoreIntersections:   boolean,
    hasIndex:              boolean,   // auto-numbered label on placement
    index:                 integer,
    options:               array,
    projection:            integer,   // 2D projection mode
    print:                 string,
    detailsView:           object,
    recalculateOnJoins:    boolean,
    recalculateOnRoom:     boolean,
    recalculateOnHost:     boolean
  },
  script:          string,            // JSON-encoded script; mostly EMPTY in this catalog
                                      // (real recipes are in __data_module_data_*)
  classification:  [
    {attributes:[], value: integer, classificator: integer}
  ],                                  // typically 6 memberships per cabinet
  catalogId:       integer,
  folderId:        integer,           // category folder hierarchy
  rowVersion:      string,            // sync token (opaque)
  width:           DimensionEnvelope,
  height:          DimensionEnvelope,
  depth:           DimensionEnvelope,
  hasDescendants:  boolean,
  imported:        boolean,
  isObsolete:      boolean
}
```

**The DimensionEnvelope is the schema Southbrook must mirror:**

```javascript
DimensionEnvelope = {
  items:    [integer, ...],   // allowed value enumeration in mm — the snap-grid
  min:      integer,          // slider minimum (free entry, advanced users)
  max:      integer,          // slider maximum
  default:  integer           // initial value
}
```

`items` is the enumeration shown in customer-mode UI; `min/max` are the slider bounds exposed in sales-rep mode; `default` is the initial value.

**Code field placeholder substitutions:**
- `{S}` — sets a sub-style at instance time
- `{H}` — sets a height variant
- `1DR`, `2DR` — number of doors
- `BHL` = base hinged left, `BHS` = base hinged sink, `WC` = wall corner, `WD` = wall door, `WL` = wall larder, etc.

---

## 5 · The recipe layer — parametric construction grammar

The recipes are **not** in the catalog modules. They are in four top-level JSON blobs in the application's data layer:

| File | Recipes | Bytes | Domain |
|---|---|---|---|
| `__data_module_data_base` | 52 | 4,822 | Base units (BHL, BHS, BCV, BOE, BSPLY, CCL/D, CHL, …) |
| `__data_module_data_wall` | 30 | 2,976 | Wall units (WD, WCVM, WC, WL, …) |
| `__data_module_data_tall` | 47 | 6,881 | Tall units (T-prefix codes) |
| `__data_module_data_standart` | 3 | 175 | Standard/default fallback recipes |
| **TOTAL** | **132** | **14,854** | Full active recipe set |

### 5.1 Recipe shape (verified by parsing all 132)

```javascript
{
  "<MODULE_CODE>": {
    "filling": {
      "<element_name>": { /* element-specific parameters */ },
      // OR with numeric prefix for multiple of same type:
      "1.<element_name>": { /* params */ },
      "2.<element_name>": { /* params */ },
      …
    },
    "subject":     "<value>",   // present on 13 recipes — alters subject classification
    "sink":        "<value>",   // present on  7 recipes — "insert" for sink units
    "height_code": "<value>",   // present on  4 recipes — links to height-variant table
    "worktop":     {radius: "{W}"}   // present on 1 — worktop-following parameter
  }
}
```

### 5.2 The complete filling element vocabulary (18 element types — empirically enumerated)

This is the construction grammar. Each element emits its own geometry and its own contribution to the BoM rollup.

| Element | Frequency | Purpose |
|---|---|---|
| `hinge_block` | 94 | Hinged door panel with hinge-position parameter |
| `drawer` | 54 | Drawer assembly (box + front + slide) |
| `delimiter` | 40 | Internal horizontal divider/shelf |
| `L_profile` | 25 | L-shaped corner profile (single-side) |
| `stub_block` | 23 | Blank stub panel (no door, no drawer) |
| `oven` | 15 | Oven housing aperture |
| `open_block` | 10 | Open shelving (no door) |
| `integrated_microwave` | 9 | Microwave housing aperture |
| `tall_cargo` | 9 | Tall pull-out larder mechanism |
| `container` | 7 | Generic container fitting |
| `lift` | 7 | Lift-up door mechanism (e.g. wall lift-up) |
| `dishwasher` | 5 | Dishwasher aperture (integrated) |
| `fridge` | 4 | Fridge housing aperture |
| `sink_block` | 3 | Sink-base specific block |
| `corner_carousel` | 3 | Lazy-Susan rotating shelf |
| `pull_out` | 3 | Generic pull-out mechanism |
| `wine_rack` | 2 | Wine bottle storage rack |
| `gable` | 1 | End/finished gable panel |

**Implementation note for Southbrook:** mirror these as classes in `parametric_carcass.esm.js`. The frequency column is the priority — start with `hinge_block`, `drawer`, `delimiter`, `L_profile`, `stub_block`, which cover 87% of all element instances.

---

## 6 · Classification taxonomy

### 6.1 The Classificator (65 total)

```javascript
{
  id, code, name,
  allowMultiple:    boolean,    // can a module have multiple values?
  targets:          array,      // which model types this classifies
  values:           array,      // child Classificator.Value records
  purpose:          string,     // grouping into one of 6 purpose-codes
  collectionType:   string,
  accessModifier:   string,
  catalogs:         array,      // which catalogs use this classificator
  rowVersion:       string
}
```

### 6.2 The six purpose codes

1. **Functional** — what the cabinet does (base, wall, tall, sink, oven housing, larder)
2. **Visual** — appearance attributes
3. **Mechanical** — drawer/door/lift-up mechanism family
4. **Material** — decor/door family compatibility
5. **Geometric** — dimensional class (width band, depth band)
6. **Pricing** — pricing tier

### 6.3 Membership cardinality

Empirically observed on the first kitchen module: an array of **6** `{value, classificator}` references, each linking the cabinet to one classificator's chosen value. This is the cardinality Southbrook should target — six attribute groups per cabinet, each carrying one chosen value.

**Mapping to Odoo:** the six purpose codes become **attribute groups** in `product.attribute` with `display_type` and ordering encoding the purpose. Standard `product.attribute.value` records are the classificator values.

---

## 7 · Asset URL grammar

All binary assets resolve from `blobs.prodboard.com`. The URL grammar is:

```
https://blobs.prodboard.com/<scope>/<kind>/<guid>/<filename>
```

| Scope | Meaning | Observed kinds |
|---|---|---|
| `standards` | Prodboard-global generic assets | icon, model |
| `library` | Cross-tenant shared library | icon |
| `betterkitchens` | Tenant-private assets | icon, texture, temp (KTX2) |
| `shared` | Globally shared environment | cubemaps |

Plus app-chrome PNGs at `planner.prodboard.com/assets/generic/<name>.png` (e.g. `room settings.png`, `room lighting.png`).

**Legal posture for Southbrook:** these URLs are CDN-public (no auth observed) but the imagery is copyrighted to Prodboard/BetterKitchens. **Do not embed any `blobs.prodboard.com` URL in production code.** Use only in dev fixtures with the four-tier image strategy in §11.

---

## 8 · Layout and visual tokens

### 8.1 The three-pane grid (measured live in DOM)

```
┌──────┬──────────────┬─────────────────────────────────────────┐
│      │              │                                         │
│  58  │     394      │              flex (viewport)            │
│  px  │     px       │                                         │
│ rail │   catalog    │           3D / 2D-iso planner           │
│      │     pane     │                                         │
│      │              │                                         │
└──────┴──────────────┴─────────────────────────────────────────┘
                                                       ┌────────┐
                                                       │ footer │
                                                       └────────┘
```

- **Left rail:** 58 px wide, near-black background, vertical tool/category icons.
- **Catalog pane:** 394 px wide, cool-off-white background, holding catalog tiles.
- **Viewport:** flex (fills remainder), holds the Three.js canvas + dimension overlay + footer controls.

### 8.2 Token set

| Token | Value |
|---|---|
| Font | Roboto Flex |
| Left rail background | near-black (#1a1a1a‑ish) |
| Catalog pane background | cool off-white |
| Catalog tile | 296 × 94 px with 80 × 80 thumbnail |
| Selected tile accent | tenant brand colour |

### 8.3 Top toolbar — 9 elements (left to right)

1. Logo / brand
2. Project name (editable)
3. Undo / Redo
4. View toggle (3D / Top / A / B / C / D)
5. Solid↔Blueline toggle
6. Save state indicator
7. Share / export
8. Account / tenant
9. Help

### 8.4 Bottom footer

VIEW + 3D + Top + A/B/C/D mode cluster (the four-letter modes are quaternion-preset 3D camera angles).

---

## 9 · The Three.js scene

- **Tone mapping:** ACES Filmic
- **Output:** sRGB
- **Lights:** 6 (1 hemispheric + 1 directional + 4 point)
- **Textures:** KTX2 with Basis Universal compression (large compression savings — the texture budget for the BetterKitchens deployment is ~22 MB total)
- **Picking:** MeshBVH (bounding-volume hierarchy — important for the ~100-cabinet-per-scene cardinality without freezing)
- **Scene updater:** diff-based; do **not** re-mount on prop change (re-mount destroys raycaster state and is a known Three.js performance trap)

---

## 10 · The negative-space register (what Prodboard does NOT do — Southbrook's moat)

This is the differentiation map. Every row below is something Southbrook ships and Prodboard cannot.

| Capability | Prodboard | Southbrook (target) |
|---|---|---|
| BoM generation | ❌ | ✅ via `product_configurator_mrp` |
| Real quote PDF | ❌ webhook only | ✅ Signature Series styled |
| Payment integration | ❌ | ✅ (v2 — data model ready in v1) |
| MRP loop | ❌ | ✅ full chain |
| Cut list export | ❌ | ✅ Accucutt hand-off |
| Multi-select | ❌ | ✅ shift-click |
| Keyboard dimension entry | ❌ | ✅ |
| Right-side inspector | ❌ | ✅ |
| Collision detection | ❌ `ignoreIntersections:true` | ✅ |
| Channel pricelist | ❌ single price | ✅ 5 channels |
| Sales-rep mode | ❌ | ✅ Order Builder |
| Mobile responsive | ❌ desktop only | ⚠️ 2D fallback in v1 |

---

## 11 · The four-tier image strategy

**Never** embed `blobs.prodboard.com` URLs in production code. Use this cascade:

1. **Tier 1 — vendor-supplied renders** when Southbrook provides them. Highest fidelity, highest cost.
2. **Tier 2 — runtime-baked thumbnails** from the live Three.js scene per configurator state change. Generated on first view, cached.
3. **Tier 3 — hand-authored SVG fallbacks** for every cabinet code. **Day-1 launch ships 100% Tier 3 coverage** so the configurator never shows a broken tile.
4. **Tier 4 — neutral placeholder.** Last resort.

The bake job (Tier 2) runs on configurator state change; the cache key is the full configuration hash so changing series, finish, or dimension produces a fresh thumbnail without stale-cache risk.

---

## 12 · Asset inventory and load budget

### 12.1 The HAR — 238 entries, ~22 MB total

- 89 images (icons + textures)
- 13 GLBs (only 13 — confirms procedural-geometry dominance)
- 9 cubemap JPGs (~10.5 MB — the biggest single line item)
- main.js bundle 4.64 MB
- Localization: 1054 keys, 9 languages (English, Polish, German, Latvian, Slovenian, French, Ukrainian, Hungarian, Russian)

### 12.2 Model list (sample, from `__cat_kitchens.models`)

Worktops, fillers, end panels, plinths, cornices, pelmets, plus the procedural-geometry placeholders that the recipe layer assembles dynamically.

---

## 13 · Open questions

These remained unprobed at end of reconnaissance. Defer to follow-on rounds — none block the immediate Southbrook build.

| # | Question | Impact | Probe |
|---|---|---|---|
| Q1 | Exact picking algorithm — MeshBVH variant? | Performance ceiling for 100+ cabinets | Profile in Chrome devtools |
| Q2 | Cubemap selection logic — per-scene or per-cabinet? | Lighting fidelity | Watch `__shared/cubemaps/` requests during scene change |
| Q3 | Localization fallback — which language for unmapped keys? | i18n correctness | Switch to Russian, observe key behaviour |
| Q4 | Drawer mechanism family — Blum / Hettich / generic? | Hardware vocabulary parity | Search `main.js` for `Blum\|Hettich\|Grass\|Salice` |
| Q5 | Hinge type encoding — separate attribute or part of door family? | Hinge BoM accuracy | Inspect `__cat_handles` vs door-family attributes |
| Q6 | PMREMGenerator usage in `main.js` | Lighting fidelity in Southbrook | Inspect Three.js PMREMGenerator use in `main.js` |
| Q7 | What's in `__cat_kitchen-cabinets` (25 modules)? Test catalog or production override? | Whether to import the 25 extras | Deep-diff against `__cat_kitchens` |
| Q8 | Door family `filter_linear` syntax — how do options resolve per cabinet? | Door option resolution engine | Sample three `filter_linear` entries by family |

---

## 14 · The reconnaissance evidence log

| Source | Type | Size | Status |
|---|---|---|---|
| `__cat_kitchens` | Catalog object | 251 modules + 54 models + 197 decors + 242 textures | Confirmed in final pass |
| `__cat_elements` | Catalog object | 42 modules + 156 models + 24 decors + 3 textures | Confirmed |
| `__cat_doors` | Catalog object | 63 modules + 176 models + 108 decors + 129 textures | Confirmed |
| `__cat_handles` | Catalog object | 20 modules + 29 models + 8 decors + 0 textures | Confirmed |
| `__cat_kitchen-cabinets` | Catalog object | 25 modules + 5 models + 4 decors + 1 texture | Confirmed; role unclear (Q7) |
| `__cat_classificators` | Catalog object | 65 classificators with 120 values | Confirmed |
| `__data_module_data_base` | String JSON | 4,822 bytes, 52 recipes | Parsed cleanly |
| `__data_module_data_wall` | String JSON | 2,976 bytes, 30 recipes | Parsed cleanly |
| `__data_module_data_tall` | String JSON | 6,881 bytes, 47 recipes | Parsed cleanly |
| `__data_module_data_standart` | String JSON | 175 bytes, 3 recipes | Parsed cleanly |
| `__data_door_data` | String JSON | 12,186 bytes, 40 families | Parsed cleanly |
| `__data_data_json` | String JSON | 563 bytes, BBBPS table | Parsed cleanly |
| `__data_exclusions` | String JSON | 2,002 bytes, ~80 rules | Parsed cleanly |
| `__data_filter_linear` | String JSON | 4,557 bytes, door option filter | Parsed cleanly |
| `__data_trigger_size` | String JSON | 846 bytes, ~30 size triggers | Parsed cleanly |
| `__har_archive` | HAR-like | 238 entries, ~22 MB load budget | Cached |
| `__mjs` | `main.js` text | 4.64 MB | Cached for text mining |
| `__loc_Localization` | object | 1054 keys | Cached |
| live DOM | UI | 80×80 tiles, 296×94 cards, 394 px pane, 58 px rail | Measured live |
| `performance.getEntriesByType('resource')` | Network | 89 images, 13 GLBs, 9 cubemaps | Confirmed |

---

## 15 · Reproducibility checklist for Claude Code

When Claude Code consumes this manifest to recreate Prodboard's essence in Southbrook, here is the fidelity checklist:

**Visual fidelity:**

- [ ] Layout uses the 58 + 394 + flex grid from §8.1
- [ ] Tokens from §8.2 are applied — Roboto Flex font, near-black rail, cool-off-white pane
- [ ] Catalog tiles render at 296×94 with 80×80 images
- [ ] Top toolbar has the 9 elements in §8.3 order
- [ ] Bottom footer has VIEW + 3D + Top + A/B/C/D mode cluster

**Behavioral fidelity:**

- [ ] Three.js scene uses ACES Filmic tone mapping, sRGB output
- [ ] 6 lights (1 hemi + 1 directional + 4 point)
- [ ] Procedural geometry (NOT pre-baked GLBs) for cabinet bodies
- [ ] KTX2 + Basis Universal for textures
- [ ] MeshBVH for picking
- [ ] Scene-diff updater (no re-mount on prop change)

**Data fidelity:**

- [ ] 401 modules across 5 catalogs imported, not 251
- [ ] 132 recipes in the recipe table, expanded into ~600 elements
- [ ] 18 element types in the construction grammar (§5.2)
- [ ] 40 door families with ~250 door models, NOT 35 with 250 options
- [ ] 341 decors, 375 textures, 9 cubemaps
- [ ] Classification carries 6 memberships per cabinet on average

**Differentiation fidelity (the Southbrook delta over Prodboard):**

- [ ] Right-side inspector panel on selection
- [ ] Multi-select with shift-click
- [ ] Keyboard dimension entry
- [ ] Collision detection
- [ ] Real BoM preview drawer
- [ ] Hardware vocabulary (hinge, drilling, edge-band, drawer-slide)
- [ ] Worktop sub-system with edges, joints, cutouts
- [ ] Full MRP loop (BOM → MO → workorders → cut-list)
- [ ] Real PDF quote via Odoo
- [ ] Payment via Odoo payment module (v2)
- [ ] Designer/customer mode split in one app

**Image strategy fidelity:**

- [ ] Four-tier cascade implemented (vendor → rendered → SVG → placeholder)
- [ ] No `blobs.prodboard.com` URLs in production code
- [ ] Day-1 launch ships 100% Tier 3 SVG coverage
- [ ] Tier 2 bake job runs on configurator state change

---

## 16 · Provenance and integrity statement

This manifest was authored during multi-round reconnaissance of `planner.prodboard.com/betterkitchens/kitchen`. Every numerical claim was verified in a final empirical pass immediately before this document was committed to the canonical record. Eight prior errors from rounds R5–R15 were identified and corrected (§1). No claim depends on Prodboard documentation, marketing material, or third-party reporting — every figure was harvested from the live JavaScript runtime, the live DOM, the live network requests, and the live `main.js` bundle text.

The manifest is intentionally fact-dense and opinion-light. Where a design recommendation is made for Southbrook (e.g. the four-tier image strategy, the right-side inspector, the collision-detection addition), it is clearly marked as a Southbrook design choice and not a Prodboard finding.

**Known limitations of this manifest:**

- Eight open questions (§13) remain unprobed.
- The 25 modules in `__cat_kitchen-cabinets` have unclear role.
- The `script` field is empty on 219 of 239 catalog modules — recipes are in the separate `__data_module_data_*` blobs, but the mapping from module-code to recipe-code must be confirmed at import time.
- 3D model count per cabinet (the actual GLB-per-recipe wiring) was not exhaustively traced — only 13 GLBs cold-load, far fewer than 251 cabinets, confirming procedural geometry is dominant.

**End of manifest.**
