# Southbrook Materials — Phase-2 Procurement Design Spec

**Date:** 2026-07-25
**Status:** Approved (decisions settled via blindspot/ReAct ≥7/10 pass + 3 user forks + data answer). Not yet planned/built.
**Deploy target:** Live Southbrook v19 CE (`southbrook` DB, system-docker) — Materials app is already live (Phase-1).

## Goal
Make the Materials app **assist deciding the ordered quantity** of materials when demand arises, so the correct amount is purchased in the vendor's purchase UoM — using Odoo's **native** procurement, not a bespoke PO engine. Scope: demand→purchase-qty conversion (area/length/weight → sheets/rolls/kg/each) with per-family waste + ceiling round-up, surfaced as an **assist** (suggested qty on a draft RFQ a human confirms).

## How we got here
A multi-agent blindspot + ReAct pass scored 93 candidates; only **2 cleared ≥7/10**, and the synthesis then **read the live modules** and corrected the candidates' assumptions. Full record: `~/Downloads/Material Module folder/Materials Phase-2 (Procurement)/` (decisions log + workflow result).

## Three code-verified facts (reshape the scope — Phase-2 is mostly wiring)
1. **The waste model already exists and is seeded but unread.** `southbrook.kitchen.material.waste_pct` (material override) + `material.family.default_waste_pct` (family fallback, seeded e.g. 12% ewood / 15% veneer in `sb_material_core/data/material_family_data.xml`) are defined and shown on the form, but **no code reads them**. Phase-2 waste work = "turn on dormant fields," not design a model. (This is the deferred B-2.)
2. **The material→purchasable-SKU mapping already exists.** `product.attribute.value.material_id → southbrook.kitchen.material`, and `product.product._resolve_material()` resolves any BoM component back to its material; that same component `product.product` is exactly what `material.cost.source._resolve()` already prices via `product._select_seller()` / `product.supplierinfo`. **The purchasable SKU is the BoM component product.** Phase-2 only **populates `supplierinfo`** — no bridge table.
3. **The real blocker is the hardcoded qty=1 stub.** `product_configurator_mrp/models/product_config.py` writes `bom_line_vals = {'product_id': product.id, 'product_qty': 1}` for every attribute-linked component. So for **continuous families** (sheet goods, edgebanding, tile/drywall, stone) native demand is a size-blind "1 per cabinet"; for **hardware** (`per_unit`) qty=1 is already correct and must not be touched.

## Locked decisions

### User forks (answered)
| Fork | Decision |
|---|---|
| **Blast radius** | **A — new field.** Add `material_demand_qty` that drives procurement; leave the native BoM line `product_qty` untouched (non-invasive; no change to what live Manufacturing screens show). |
| **Rounding** | **Ceiling round-UP uniformly** across all families (never install a fraction of a sheet; excess → on-hand for the next job). |
| **Assist vs automate** | **Assist-only.** Suggested qty shown transparently on a native **draft PO/RFQ**; a buyer confirms via the native gate. Auto-confirm-below-threshold deferred. |
| **Yield data** | **Net-new data entry.** Per-vendor `uom_yield_qty` + supplier `uom_po`/`min_qty`/`packaging` are not recorded today → Phase-2 includes a per-material/vendor **data-collection task**. |

### Design decisions (≥7/10 synthesis, code-grounded)
- **`material_demand_qty`** — new stored computed field on `mrp.bom.line`, in `material.base_uom_id` (m²/lm/kg), for **continuous families only** (`weight_source in {density_volume, density_area, linear_density}`). Reuses the existing `_panel_volume_mm3`/`_weight_for_qty` geometry pipeline but stops at a base-UoM quantity instead of collapsing to `weight_kg`. For `per_unit`/`none`, leave it equal to the native `product_qty` (hardware count model is already correct).
- **No new mapping model** — populate `product.supplierinfo` on the existing component products.
- **`product.supplierinfo.uom_yield_qty`** — one new float ("base-UoM quantity obtained from one purchase-UoM unit", e.g. 32 ft² per 4×8 sheet). Because sheet-good yield is a per-SKU fact, **not** a fixed `uom.uom`-category ratio.
- **Purchase qty = CEIL( `material_demand_qty` × (1 + effective_waste% / 100) / `uom_yield_qty` )**, left in the vendor's `uom_po`.
- **Waste wiring** — `waste_pct` (material) / `default_waste_pct` (family) applied as a **structural** multiplier BEFORE rounding; kept **separate** from `mrp.production.scrap_factor` (operational, human-entered, display-only). Two numbers, two stages, no composition conflict.
- **Native integration only** — set `route=Buy` on each material component product; maintain `stock.warehouse.orderpoint` reordering rules per material product per warehouse (min/max derived from the `material_demand_qty` rollup across open MOs); let the native scheduler (`_run_scheduler → procurement.group → stock.rule → _run_buy`) generate the RFQ/PO. **Zero PO-creation code**; reject any `_make_po_select_seller`-style private override.
- **Estimate-grade, forward-only** — reconciling suggested vs actual `stock.move` consumption (to re-tune `waste_pct`) is deferred to a later variance phase.
- **Data model total** — 2 new fields (`mrp.bom.line.material_demand_qty`, `product.supplierinfo.uom_yield_qty`) + wire 2 dormant fields; orderpoints are native config. No new models.

## Prerequisites (blocking — in order)
1. **Geometry writeback** — `product.config.line` already calls `mrp.bom._compute_panel_dimensions()` at config time; extend that call site to **persist `width_mm`/`height_mm`/`depth_mm`** onto the configured `product.template`/`product.product`. Until this lands, `_panel_volume_mm3()` returns 0.0 and every downstream number is meaningless. **Single highest-leverage item** (also lights up the Phase-1 dormant weight KPI).
2. **Per-line consumption qty for continuous families** — the new `material_demand_qty` (Fork 1: new field, leave native `product_qty=1`), scoped to continuous `weight_source` only.
3. **Supplierinfo populated** per material component product: `uom_po`, `min_qty`, `product.packaging`, and the new `uom_yield_qty` — **net-new data entry** (largely a purchasing-data task, parallelizable with code).
4. **`route=Buy` + orderpoints** configured per material component product per warehouse.

## Sequencing
1. Geometry writeback → 2. `material_demand_qty` (continuous families) → 3. wire `waste_pct`/`default_waste_pct` + ceiling round-up → 4. populate supplierinfo (data entry, parallel) → 5. `route=Buy` + orderpoints + native scheduler → first end-to-end draft RFQ → 6. assist-layer transparency UI ("needs 3.2 sheets → order 4, incl. 12% waste") on the draft PO line + a Materials tab.

## Out of scope / deferred
- Auto-confirm-below-threshold (Fork 3 later add).
- Actual-vs-estimate variance reconciliation / waste-% self-tuning.
- Nesting/cutlist yield optimization (would replace the flat waste % — Phase-4-style).
- Process/continuous-manufacturing batch/lot demand semantics (this design is discrete-native).
- Multi-currency vendor price conversion.

## Notes
- Everything stays generic on the material master / `res_model`/`res_id`; no kitchen-specific procurement logic.
- The `product_configurator_mrp` `product_qty=1` stub is intentionally **left in place** (Fork 1); the new field drives procurement while Manufacturing's native BoM line is untouched. A later, deliberately-migrated pass could reconcile the two if desired (documented split-brain).
