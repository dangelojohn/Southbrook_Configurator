# Materials Hardware — Design Spec

**Module:** `sb_materials_hardware`
**Target:** Odoo 19 Community Edition, `~/southbrook-v19cr/addons/`
**Date:** 2026-07-25
**Status:** Awaiting user review

---

## 1. What this builds

A **faceted, spec-first catalog** for Southbrook's hardware, tooling and shop consumables,
delivered as an internal Odoo backend application.

It reproduces the UX of `reference/UX_TEMPLATE_materials_catalog.html` — the interactive
simulation of the original Blacklining `materials_ce` storefront — as an OWL client action:
masthead search, breadcrumb, category rail, multi-select facet chips, a dense sticky-header
one-row-per-variant table, and a spec-grid detail panel with an engineering side panel.

**The focus is hardware.** Fasteners, adhesives, abrasives, cutting tooling, finishing
supplies, shop consumables. Not a general materials browser that happens to include hardware.

## 2. What this does not build

The domain is already modelled. `southbrook_mrp_kitchen_tools` (v19.0.0.4.0) ships 16 models,
10 view files and 9 test files covering a 101-record category tree, 61 typed spec fields on
`product.template`, substrate compatibility, consumption tracking and stock thresholds. What it
lacks is any browsable catalog.

Therefore this module defines **no taxonomy, no spec fields, no consumption model, no cost
resolution**. It reads existing records and presents them. Duplicating that data would recreate
the twin-maintenance trap that makes the Blacklining app's `materials` / `materials_ce` fork
require every fix twice.

Also out of scope for Phase 1: search synonyms, product imagery, the Marathon workbook import,
any customer- or dealer-facing catalog, sheet goods and stone (that is `sb_material_core`'s
domain), and any modification to or refactoring of `southbrook_mrp_kitchen_tools`.

## 3. Architecture

### 3.1 Shell and providers

The catalog shell is domain-agnostic. It renders whatever a provider returns, which is what
lets Phase 2 add functional hardware without touching the frontend:

```
materials.catalog.provider   (AbstractModel — the contract)
    get_catalog(scope, category_id, facets, search, offset, limit) -> payload
        ├── tools.catalog.provider      Phase 1 — southbrook_mrp_kitchen_tools data
        ├── hardware.catalog.provider   Phase 2 — southbrook_hardware_catalog data
        └── flat.material.provider      later — sb_material_core data
```

This mirrors the provider indirection used by `mrp_process_explorer` (in the external
`realpublish-ai/odoo-addons` repo, not available locally — the pattern is reproduced, not
imported).

### 3.2 Payload contract

`get_catalog()` returns a single dict. The frontend reads only these keys:

| Key | Type | Contents |
|---|---|---|
| `ok` | bool | False plus `reason` when the provider cannot serve; never raises |
| `categories` | list | `{id, name, parent_id, count, has_children}` — the rail tree |
| `facets` | list | `{key, label, type, values[]}` where type is `enum` \| `range` \| `m2m` |
| `columns` | list | `{key, label, align, sortable}` — table columns for this category |
| `rows` | list | one dict per variant, keyed on `product_id`, values per column key |
| `detail` | dict | `{title, subtitle, specs[], engineering[], badges[]}` for the selected row |
| `total` | int | row count before pagination |
| `provenance` | str | honest statement of what the data is and is not |

**Contract rules**, learned from the `material.explorer` provider:

- Rows are keyed on `product_id`. A missing or renamed key makes rows silently unselectable.
- The whole payload build is wrapped so any failure degrades to `{"ok": False, "reason": ...}`
  rather than a 500.
- Searches and reads run through the calling user's own rights. No `sudo()` on record reads —
  the catalog must not become a way to see products a user otherwise cannot.

### 3.3 Facets are declarations, not code

Each category declares which specs are filterable, in what order, and how they render. The
declaration lives in module data, so adding a facet is a data change, not a code change. No
per-category branching anywhere in the provider or the frontend.

See §4 for the Phase 1 declarations.

### 3.4 Client action

A backend OWL client action registered under a dedicated tag, reached from a menu item under
the existing Hardware/Tools menu structure. No website routes, no portal exposure — the module
adds zero public HTTP endpoints, which removes the portal IDOR class of bug structurally rather
than defending against it per route.

Odoo 19 specifics that apply: `rpc` is imported from `@web/core/network/rpc` (the `rpc` service
was removed in 19), and any `doAction` call includes an explicit `views` array.

## 4. Facet and column declarations

### 4.1 What the data gives us

`southbrook_mrp_kitchen_tools` seeds **101 categories** in an L0–L2 tree across eleven
sections, and declares **61 spec fields** on `product.template`. Every field is a plain stored
field; none is required and none is computed, so products opt in incrementally and **absent is
a real state the catalog must render honestly** rather than as zero.

Phase 1 catalogs sections **A–E**, which is where the hardware focus lies:

| Section | L0 category | Sub-tree |
|---|---|---|
| A | Cutting Tools | Saw Blades (9), CNC Router Bits (14), Drill and Boring Bits (12) |
| B | Fasteners and Assembly Consumables | Screws (10), Fasteners (13) |
| C | Adhesives, Glues, Sealants | 12 L1 categories |
| D | Abrasives and Surface Preparation | 8 L1 categories |
| E | Finishing and Paint Tools | 9 L1 categories |

Sections F–K (measuring, clamps and jigs, hand and power tools, maintenance supplies, PPE,
packing) remain browsable through the same rail with the generic column set, but get no
bespoke facets in Phase 1.

### 4.2 Columns are declared per L1 category

Column sets differ by what the category actually is — a saw blade and a bottle of glue share
almost no specs. The rail selection determines the column set, exactly as the reference UX
does. Generic columns (name, internal reference, vendor SKU, on-hand, price) always appear.

| Category branch | Columns beyond the generic set |
|---|---|
| Saw Blades | `x_southbrook_blade_diameter_mm`, `_tooth_count`, `_kerf_width_mm`, `_bore_size_mm`, `_material_grade`, `_coating` |
| CNC Router Bits | `x_southbrook_cutting_diameter_mm`, `_shank_diameter_mm`, `_cutting_length_mm`, `_overall_length_mm`, `_coating`, `_rotation_speed_max`, `_feed_rate_max` |
| Drill and Boring Bits | `x_southbrook_cutting_diameter_mm`, `_shank_diameter_mm`, `_overall_length_mm`, `_material_grade` |
| Screws | `x_southbrook_screw_size`, `_screw_length_mm`, `_head_type`, `_drive_type`, `_thread_type` |
| Fasteners | `x_southbrook_screw_size`, `_screw_length_mm`, `_compatible_material_ids` |
| Adhesives | `x_southbrook_glue_type`, `_open_time_min`, `_cure_time_min`, `_shelf_life_days` |
| Abrasives | `x_southbrook_grit`, `_compatible_material_ids` |
| Finishing | `x_southbrook_shelf_life_days`, `_storage_temperature_notes`, hazard badges |

### 4.3 Facet declarations

Facet types: `enum` (chips from a Selection), `enum_distinct` (chips from distinct stored
values of a Char), `range` (numeric min/max), `m2m` (chips from a relation), `flag` (boolean).

| Category branch | Facets |
|---|---|
| **Screws** | `_thread_type` (enum, 8 values incl. `confirmat`, `euro`, `particleboard`) · `_head_type` (enum, 11) · `_drive_type` (enum, 9) · `_screw_size` (enum_distinct) · `_screw_length_mm` (range) · `_compatible_material_ids` (m2m) |
| **Fasteners** | `_compatible_material_ids` (m2m) · `_screw_length_mm` (range) · `_preferred_vendor_id` (m2m) |
| **Saw Blades** | `_blade_diameter_mm` (range) · `_tooth_count` (range) · `_bore_size_mm` (enum_distinct) · `_material_grade` (enum_distinct) · `_coating` (enum_distinct) · `_compatible_material_ids` (m2m) |
| **CNC Router Bits** | `_cutting_diameter_mm` (range) · `_shank_diameter_mm` (enum_distinct) · `_cutting_length_mm` (range) · `_coating` (enum_distinct) · `_compatible_material_ids` (m2m) |
| **Drill and Boring Bits** | `_cutting_diameter_mm` (range) · `_shank_diameter_mm` (enum_distinct) · `_overall_length_mm` (range) · `_material_grade` (enum_distinct) |
| **Adhesives** | `_glue_type` (enum, 12) · `_open_time_min` (range) · `_cure_time_min` (range) · `_shelf_life_days` (range) · `_hazardous` / `_flammable` / `_requires_ventilation` (flag) · `_compatible_material_ids` (m2m) |
| **Abrasives** | `_grit` (enum_distinct, numeric-ordered) · `_compatible_material_ids` (m2m) |
| **Finishing** | `_hazardous` / `_flammable` / `_requires_ventilation` / `_msds_required` (flag) · `_shelf_life_days` (range) |
| **All categories** | `_tool_family` (enum, 32) · `_directness` (enum, 7) · `_preferred_vendor_id` (m2m) |

`_compatible_material_ids` is the substrate axis — the "screws specific to wood types"
requirement that started this build. It appears on every branch where substrate governs
selection, which is most of them.

### 4.4 The Char-that-is-a-number problem

`_grit`, `_screw_size`, `_material_grade`, `_shank_diameter_mm` values and `_coating` are
`Char`. Grit especially must sort **80, 100, 120, 150, 220** and not **100, 120, 150, 220, 80**.

The provider normalises: parse a leading number for ordering, keep the original string for
display. Values that do not parse sort **last**, retain their label, and are never silently
dropped — a facet chip that quietly disappears is worse than one that sorts oddly.

This normalisation lives in the provider, not in the data. No field is added to
`southbrook_mrp_kitchen_tools`.

### 4.5 Detail panel mapping

The reference UX's spec grid and engineering side panel map onto:

- **Spec grid** — the selected category's column fields, each labelled, with absent values
  rendered as an explicit dash rather than `0` or blank.
- **Engineering rail** — `_preferred_vendor_id`, `_vendor_sku`, `_issue_uom_id`,
  `_min_stock_qty` / `_max_stock_qty` / `_reorder_multiple`, `_estimated_life_qty` +
  `_estimated_life_unit`, `_sharpening_interval_qty`, `_calibration_interval_days`,
  `_inspection_interval_days`, and `_tool_lifecycle_state` as a status badge.
- **Badges** — `_hazardous`, `_flammable`, `_msds_required`, `_requires_ventilation`,
  `_expiry_required`, `_ppe_required`. Safety flags read at a glance or they are not doing
  their job.

## 5. Security

- No new models means no new `ir.model.access.csv` rows for domain data.
- The client action and its menu are visible to internal users; no new group is created unless
  a reviewer identifies one is needed.
- Record access is the calling user's own throughout. The provider never elevates.
- No public routes.

## 6. Testing

Following `southbrook_mrp_kitchen_tools` and `sb_material_core` conventions —
`TransactionCase`, `@tagged("post_install", "-at_install", "southbrook", ...)`, fixtures via
`env.ref()` on seeded XML ids and `create()` for dynamic records.

| Test | Asserts |
|---|---|
| `test_provider_contract.py` | Payload contains every required key; rows keyed on `product_id`; column keys match row keys |
| `test_provider_degrades.py` | A missing model, an empty category and a bad facet key each return `{"ok": False, reason}` — never an exception |
| `test_facet_filtering.py` | Each facet type (enum, range, m2m) narrows the result set correctly; multi-select within a facet is OR, across facets is AND |
| `test_category_tree.py` | Rail tree is built from `southbrook.tool.category`, counts are correct, and a category with children is navigable |
| `test_search.py` | Search matches name, internal reference and SKU, and is case-insensitive |
| `test_access.py` | A user without rights to a product does not see it in rows — the provider does not elevate |

## 7. Phasing

| Phase | Delivers | Touches existing code |
|---|---|---|
| 1 | Catalog over `southbrook_mrp_kitchen_tools` data | Nothing |
| 2 | `southbrook_hardware_catalog` records as a second provider | Reads only |
| 3 | Consolidating the two hardware modules — only if the seam proves annoying | Yes, deferred deliberately |

## 8. Risks and honest limits

- **The catalog is only as good as the data.** Where spec fields are unpopulated, facets will
  be sparse. The catalog must show a spec as absent rather than implying a value.
- **The UX is reimplemented, not ported.** The original is server-rendered QWeb; this is OWL.
  Visual fidelity is a review criterion, and the reference simulation is the acceptance target.
- **`mrp_process_explorer` is not available locally**, so the shell is built fresh rather than
  extended. If that repo is later vendored in, some of this becomes redundant.
- **Deferred from an earlier decision:** extracting `material.cost.source` into
  `sb_material_base` was approved when the design still needed cost resolution. A read-only
  catalog does not. The extraction remains sound housekeeping but is no longer part of this
  build — confirm at review.

## 9. Definition of done

1. The client action renders the reference UX: rail, facets, table, detail.
2. Facet declarations exist for every Phase 1 category with populated specs.
3. All tests in §6 pass.
4. No new public routes; no `sudo()` on record reads.
5. A code snapshot and the build ledger are in the build record folder.
6. Delivered per §10.

## 10. Delivery

`sb_materials_hardware` ships as a **standalone, separately installable module** — its own
directory under `addons/`, its own manifest, installable without any part of this build being
merged into another module.

On completion it is pushed to **both remotes**, matching how the rest of the Southbrook work is
mirrored:

- **Forgejo** — `ssh://git@192.168.68.108:2223/john/…` (on-prem, primary)
- **GitHub** — `dangelojohn/…` (private mirror)

**Installation is a gated action.** Installing on the live Southbrook instance happens only on
explicit go-ahead, and staging-first — consistent with how every other deploy in this project
is handled. The spec's definition of done covers code, tests and push; it does not assume the
install has happened.
