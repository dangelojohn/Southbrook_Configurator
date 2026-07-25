# Design Spec — Southbrook Materials app (Odoo 19 CE)

**Date:** 2026-07-25
**Author:** John (METISA) + Claude
**Deploy target:** live Southbrook Cabinetry Odoo 19 CE instance (`southbrook-odoo` under system-docker on QNAP)
**Status:** approved for spec review

---

## 1. Purpose

Rebuild the old "Materials" catalog concept as a set of **small, v19-CE-native modules** that
calculate material in MRP and expose it through a consistent **Miller-column catalog UX** across
every phase. Two calculations are in scope from day one:

- **A — Material cost rollup** on the Manufacturing Order (price-based: Σ component `price basis × qty`).
- **B — Density → weight** calculation (weight = density × computed volume), rolled up through the BoM.

The old app had density as a **display-only** field (never wired to a calculation) and a McMaster-style
website catalog. This rebuild wires density into real MRP math and revives the catalog as the app's
signature interaction pattern.

## 2. Confirmed decisions (locked in brainstorming)

1. **Hybrid material model (③):** a dedicated **Material master** holds physical/engineering properties
   (family, density, cost basis, UoM); the **native Product Configurator** selects the material via an
   attribute that maps to a Material record. Single source of truth + configurator-driven selection.
2. **Generalize the existing `mrp_process_explorer`** into the shared, provider-driven Miller-column
   shell. It is already provider-driven (`explorer_provider` context → any model with `get_data()`).
   We extend it to serve materials as well as process. **One hardened OWL component, many providers.**
3. **Native stays native:** the Product Configurator drives material *selection*; the actual
   **transactional writes** (confirm/post MO, send PO) remain on native Odoo records. The Explorer
   browses, specs, and shows calculations, then hands off to native records.
4. **Catalog UX from Phase 1** — the Miller-column Explorer is the signature surface in every phase;
   each phase supplies its own provider + detail-pane content.
5. **Phasing:** Phase 1 = core + MRP; Phase 2 = Inventory; Phase 3 = Purchasing. Later/optional:
   Scheduling, website storefront.
6. **CE-native only** — no Enterprise deps (no `mrp_plm`, `quality`, `sale_product_matrix` requirement).

## 3. Material families (taxonomy, data not code)

Configurable taxonomy, seeded but user-extensible. Initial families:
metals · engineered wood · solid wood · laminates & edgeband · glass · stone/quartz · plastics ·
concrete/cement · hardware & fasteners · adhesives & finishes.

Each family → types → materials (e.g. Engineered Wood → Plywood → Walnut Ply 18 mm). Modeled as data
so new families/materials are added without code changes (Twelve-Patterns "configuration as data").

## 4. Module architecture (layered)

```
sb_material_core       Material master: family taxonomy, density, cost basis, UoM,
                       + configurator attribute↔material mapping. Base dependency.
sb_material_mrp        Phase 1 — density→weight (B) + cost rollup (A) + yield/scrap
                       on native mrp.bom / mrp.bom.line / mrp.production.
sb_material_stock      Phase 2 — weight-on-hand, valuation, storage, on stock.move / quant.
sb_material_purchase   Phase 3 — supplier price basis, buy-in-UoM, reorder, lead time.
mrp_process_explorer   Generalized shared Miller-column shell (provider-driven).
                       Lives in realpublish-ai/odoo-addons; extended to add material providers.
```

Each module installs independently and depends only on `core` (+ the native module it extends).
This keeps deploys to the live instance incremental and each unit independently testable.

**Cross-repo note:** the material modules are Southbrook-specific (this repo). The Explorer shell
lives in `realpublish-ai/odoo-addons` (`mrp_process_explorer`, currently `19.0.1.0.21`). Generalizing
it is a change to *that* repo; the material providers can live either in the shell module or in
`sb_material_*` (decided in the plan). Both are already deployed to the same Southbrook instance.

## 5. Data model — `sb_material_core`

**`sb.material` (Material master)** — one record per real material/grade:
- `name`, `code`
- `family_id` → `sb.material.family` (the taxonomy; `parent_id` for family → type nesting)
- `density` (Float, g/cm³) — the value that drives weight; **the field the old app never used**
- `density_uom` / base UoM (`uom.uom`) — dimensional correctness (kg, m², sheet, linear m)
- `cost_basis` (Monetary) + `cost_basis_uom` (e.g. $/kg, $/sheet) — feeds cost calc
- `standards_ids` (Many2many → material standards; carried over from old `materials_ce.standard`)
- `active`, `notes`

**Native mapping:** a `product.attribute` (e.g. "Material") whose `product.attribute.value` records
each carry a `material_id` → `sb.material`. Selecting the attribute on a product/variant (via the
native Configurator) resolves to a Material record, so density/cost flow into MRP automatically.
(Reuses the old app's `product_attribute_value.numeric_value`/`short_code` extension pattern.)

## 6. Phase 1 — `sb_material_mrp` (the calculations)

On **`mrp.bom.line`** (computed, stored):
- `material_id` (resolved from the component product's material attribute)
- `component_volume` (from product dimensions / a volume field / UoM) — the volume basis
- `component_weight` = `density × component_volume × qty`
- `component_material_cost` = `cost_basis × qty` (normalized through UoM)

On **`mrp.bom`** and **`mrp.production`** (computed):
- `material_weight_total` = Σ line weights
- `material_cost_total` = Σ line costs (parity with `mrp_product_costing`'s `mat_cost`/`planned_mat_cost`)
- `scrap_factor` (%) — yield/scrap; `weight_to_purchase` = weight_total × (1 + scrap_factor)

**Parity note:** the existing `mrp_product_costing` computes price-based `mat_cost` on `mrp.production`
via `_compute_actual_material_cost` (OpenValue refactor) / `calculate_actual_material_cost`. Scope A
reproduces that behavior CE-native; we either extend that module or reimplement cleanly in
`sb_material_mrp` (decided in the plan — prefer extend/depend to avoid duplication).

**Material Summary** is rendered through the generalized Explorer (a `material.explorer` provider), not
a bespoke view: tiles (total weight, cost, scrap, to-purchase), per-component weight bars, and the
density→weight→cost table — the same layout shown in the approved simulation.

## 7. The generalized Explorer (shared UX shell)

Extend `mrp_process_explorer` so the same Miller-column OWL component serves multiple domains via
providers. Each provider exposes `get_data()` returning the documented payload contract.

| Phase | Provider (`explorer_provider`) | Detail pane |
|---|---|---|
| 1 · MRP | `material.explorer` | density→weight, cost rollup, yield/scrap; **Add to BoM / Open MO** |
| 2 · Inventory | stock provider | on-hand, weight-on-hand, valuation, locations |
| 3 · Purchasing | buy provider | suppliers, price basis, reorder, lead time; **Create RFQ** |

**Catalog navigation:** Family → Type → Material → density-first spec pane (the approved Miller
simulation). Transactional buttons in the detail pane open native records; the Explorer never posts
transactions itself.

**Reuse:** the column-resize/reflow fixes already shipped in `mrp_process_explorer 19.0.1.0.21` carry
over — no re-solving that.

## 8. UX principles

- **Native Product Configurator** for material selection (upgrade-safe, graphical, zero maintenance).
- **Miller-column Explorer** as the consistent browse/spec/calc lens across all phases.
- **Native records** for all writes (MO confirm/post, PO send) — reliability + upgrade safety.
- Density leads every material detail pane (it's the calc driver).
- Mobile: columns scroll horizontally / degrade to drill navigation (shell already handles column layout).

## 9. Deployment & ops (live Southbrook)

- Reach: `ssh qnap-tunnel` (or LAN `admin@192.168.68.108`); stack under **system-docker**.
- Install/upgrade scoped per module: `-i`/`-u <module> --stop-after-init`, then `kill -HUP 1` to clear
  ormcache; container restart when asset bundles change (bumps hash).
- Deploy addons to `/mnt/extra-addons` (host `/share/CACHEDEV3_DATA/Container/southbrook/addons`).
- Each phase deployed and smoke-tested on a real MO before the next phase starts.

## 10. Testing / acceptance (per phase)

- Unit tests for: density→weight per component and BoM rollup; cost rollup parity; scrap factor;
  attribute→material resolution; UoM normalization.
- Invalid-states standard: a material with no density/UoM must fail loud (not silently compute 0);
  weight/cost fields never render a fabricated value when inputs are missing.
- Phase 1 gate: configure a Walnut Base 600 mm MO, see correct total weight + material cost + scrap in
  the Explorer's Material Summary, matching hand calc; confirm MO posts natively.

## 11. Risks & mitigations

- **Custom-UI maintenance / upgrade exposure** → concentrate all custom UI in the *one* generalized
  Explorer shell; never sprawl into per-phase bespoke screens. Transactions stay native.
- **Volume source ambiguity** (weight needs a volume): must define per material family how volume is
  derived (product dimensions vs. sheet area × thickness vs. linear × section). **Open question, §12.**
- **Cross-repo coupling** (Explorer in odoo-addons, materials in southbrook repo) → version-pin the
  Explorer dependency; document the contract.
- **Copy consolidation:** ~6 divergent copies of the old `materials_ce` exist; we build one
  authoritative module and do not carry the copies forward.

## 12. Open questions (resolve before/within the plan)

1. **Volume basis for weight (B):** for sheet goods, is volume = cut-panel area × thickness (needs the
   cutlist dimensions), or the product's `volume` field? For cabinetry, panel area × thickness is the
   accurate path and ties to the estimating cutlist — confirm.
2. **Cost rollup home:** extend `mrp_product_costing`/OpenValue module, or implement fresh in
   `sb_material_mrp`? (Prefer extend to avoid duplicated logic — confirm.)
3. **Material providers home:** inside `mrp_process_explorer` or inside `sb_material_*`?

## 13. Phasing summary

- **Phase 1** — `sb_material_core` + `sb_material_mrp` + generalize Explorer (`material.explorer`
  provider). Density→weight + cost rollup + scrap, browsable in the Miller catalog. Deploy + smoke-test.
- **Phase 2** — `sb_material_stock` (weight-on-hand, valuation) + inventory provider.
- **Phase 3** — `sb_material_purchase` (supplier cost basis, reorder, lead time) + buy provider.
- **Phase 5** — AI-assisted Material Onboarding: an AI button that drafts new material
  categories/specs/sourcing (human vet → promote; AI = lowest trust tier). See §15.
- **Later/optional** — scheduling penetration; public website storefront.

---

## 14. Addendum — 2026-07-25 · source model, scope, blindspot resolutions

Product of a 6-agent blindspot pass (findings scored; ≥8/10 acted on) + interactive
source-planning with John. **Supersedes earlier sections where noted.**

### 14.1 Scope additions (material families)
Add: **ceramic tile / backsplash**, **countertop stone (granite/quartz)**, **countertop
laminate**, **drywall / gypsum board** (paper-faced *and* fiberglass/DensGlass). All four are
**buy / subcontracted**.

### 14.2 Make vs Buy → native product **route** drives the calc path
- **Manufacture route** → density→weight + cost (carcass sheet goods, made in-house).
- **Buy route** → area→cost **sourcing estimate** (countertops, tile, drywall, hardware…); weight N/A (the fabricator owns it).
The existing `southbrook.kitchen.material.is_subcontract_default` seeds this distinction.

### 14.3 Material master = **EXTEND `southbrook.kitchen.material`** — NOT a new `sb.material` [resolves #8]
Inspected: the model lives in `southbrook_mrp_kitchen_workcenters` with `name, code, active,
requires_finishing, can_be_edge_banded, is_subcontract_default, note`. **Extend it** (one material
model, no duplication). Add:
- `family_id` → new `material.family` taxonomy (`parent_id` nesting: Family → Type).
- `weight_source` (Selection — see 14.4).
- `density` (Float, g/cm³) = **effective density, estimation-grade ±15%** + `density_source` (material | family_default) [resolves #3].
- `base_uom`; **thickness = product variant attribute**, **facing = property** (e.g. paper | fiberglass/DensGlass) [resolves #11].
- per-family waste fields (see 14.7).
- **cost is NOT a stored field** — resolved via cascade (14.5).
The `sb_material_core` module carries these extensions and depends on `southbrook_mrp_kitchen_workcenters`.

### 14.4 `weight_source` enum [resolves #2, #3, #12]
`density_volume` (made sheet/solid wood: density × cut-panel volume) · `density_area`
(tile/drywall/stone: area × thickness × density) · `linear_density` (edgebanding: kg/m) ·
`per_unit` (hardware: kg/ea) · `none` (bought — weight not tracked). The weight formula
**dispatches on this field**; a single density×volume formula is never assumed.

### 14.5 Cost = **sourcing cascade** [resolves #6, #7, #10]
Tier 1 **vendor** (Purchasing `product.supplierinfo` + latest PO + Contacts) → Tier 2 **manual**
→ Tier 3 **online**. Behavior = **auto-default (best tier wins) + per-line override + quote-level
toggle**. Vendor tier = **snapshot-with-refresh** (freeze price+date onto the quote; badge when
>30 days; explicit "Refresh prices" action). **Every resolved number carries a provenance badge**
(vendor·PO / manual / online-est / family-default) — the honesty layer reused from the Process
Explorer. Consequence: the material master needs **no pre-loaded 5000-row cost table** [#10 dissolved].

### 14.6 Geometry sources [resolves #1]
- **Made** → cut-panel dimensions from the cutlist **at MO-time** (not `product.template.volume`).
- **Bought** → **auto-derive area / linear-ft from the design** (run length → countertop LF; wall
  area → backsplash/drywall) **+ manual override**.

### 14.7 Waste / coverage [resolves #12]
Per-family, per-line overridable, badged as estimate:
- **Made sheet goods** — flat waste % (estimate now; true nesting yield via Accucutt/cutlist bridge later).
- **Ceramic tile** — coverage/box → **round UP to whole boxes** + cut-waste %.
- **Drywall** — wall area → **round UP to whole sheets** + cut-waste %.
- **Subcontracted stone/laminate** — **0 added** (vendor SF price already includes waste) + optional seam/edge allowance.

### 14.8 Multi-level BoM rollup [resolves #5]
Weight/cost rollup uses native **`bom.explode()`** to flatten to leaf components (phantom BoMs
expand). Never sum only top-level lines — cabinet BoMs are multi-level.

### 14.9 Explorer generalization safeguards [resolves #9]
Generalize `mrp_process_explorer` on a **branch** in `realpublish-ai/odoo-addons`; **backcompat
test both providers** (existing `mrp.process.explorer` + new `material.explorer`); **staging soak**
before production; **pin the provider-contract version** in the material modules.

### 14.10 Remaining items for the implementation plan
- Unit-conversion constants + rounding (exact formula, HALF-UP, precision) [#4] — pin in plan §6.
- **Online tier** mechanics (reaches outside Odoo) — later capability; manual-assisted first.
- `currency_id` on cost cascade — add if Southbrook is multi-currency (confirm; else company currency).
- Companion/assembly materials for bought surfaces (tile: grout/thinset/backer; drywall: mud/tape/screws/bead; countertop: edge/adhesive) modeled as a small BoM per surface, not one line.

---

## 15. Phase 5 — AI-assisted Material Onboarding (an "AI Button")

**Goal:** an in-app AI action that drafts new material categories and records by researching
sources, manufacturing specifications, and costing — productizing the manual blindspot + deep-
research workflow used to design this app.

**Trigger:** an **AI Material Onboarding** button/wizard on a material family; input = a material or
category name (e.g. "cork underlayment", "fiberglass-faced drywall").

**Produces (grounded + cited):**
1. **Category placement** in the family taxonomy (creates the `material.family` node if new).
2. **Manufacturing specs** — effective density, `weight_source`, typical thickness/facing/grade variants, relevant standards (ANSI/ASTM/CARB/…).
3. **Sourcing** — candidate vendors + typical price ranges with UoM, cross-checked against Odoo Contacts/Purchasing.
4. **Blindspot / considerations report** — handling, waste behavior, make-vs-buy, compatibility.

**Guardrails (non-negotiable):**
- All output is created as **DRAFT**, badged **"AI-estimated" (lowest trust tier)** with **source citations**.
- **Human vet → promote** required before any quote use; AI numbers **never auto-live**.
- Vendor prices must be confirmed against Purchasing before leaving the online/estimate tier.
- **Idempotent** (no duplicate families/materials); **cost-aware** (LLM calls are billed).

**Engine:** **Claude** (exact model + API pinned in the implementation plan; grounded web research
+ structured output matching the material schema). Reuses the multi-agent research/blindspot pattern.

**Depends on:** Phase-1 core (material master + families) + the sourcing cascade (14.5). **Not built before Phase 1.**

