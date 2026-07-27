# Size-Aware Procurement Trigger (Fork-1 closure, Option C) — Design Spec

**Date:** 2026-07-27 · **Status:** Approved (user chose Option C per investigation
`fork1-investigation.md`; stock-replenishment model confirmed).
**Deploy target:** live `southbrook` (Odoo 19 CE).

## Goal
Make the native procurement TRIGGER fire on real material demand — without touching
`mrp.bom.line.product_qty`, MO screens, consumption/backflush, or valuation.

## Context (verified live 2026-07-27)
- The trigger is not wired at all today: none of the 6 sheet components has
  `route=Buy` or an orderpoint (the Phase-2b helpers exist but were never activated).
- `product_qty=1` deliberately stays (Fork-1): it feeds shop-floor semantics and the
  material-app computes (geometry encodes size); writing size into it would
  double-count and move valuation (see investigation §4).
- Stocking UoM is mixed: SBK-SHEET-* = m², RM-* = Units (cleanup noted, not blocking:
  orderpoint min/max are expressed in the product's own UoM either way).

## Design (Option C — additive, reversible)
1. **Orderpoint MIN from demand** — extend the existing
   `action_sb_sync_orderpoint_max` (sb_material_mrp) into a full min/max sync:
   MIN = the open-MO `material_demand_qty` rollup expressed in the product's UoM
   (same conversion ladder as MAX: native UoM → `uom_yield_qty` CEIL → skip+log);
   MAX ≥ MIN (keep existing MAX logic; clamp MAX to at least MIN). Renaming to
   `action_sb_sync_orderpoints` acceptable with a delegating alias for backcompat.
   Honesty: products with no demand/material/conversion are skipped, never fabricated.
2. **Activation** (live data via the sanctioned deploy/migration path, not ad-hoc):
   a migration (in sb_material_mrp, per the cross-module field-order lesson) that,
   for the 6 known sheet components (by default_code), applies `route=Buy`
   (`action_sb_set_route_buy`) and runs the orderpoint sync. Idempotent; skips
   absent products.
3. **End-to-end proof** (test, synthetic): open MO with real demand → sync → orderpoint
   MIN>0 → `stock.rule.run_scheduler` → draft RFQ exists for the component, qty in
   purchase units. Auto-confirm stays default-OFF; buyer confirms natively.

## Non-goals (unchanged)
No `product_qty` change; no MTO; no consumption/valuation change; no auto-confirm
default change. Option A ("true consumption & valuation") remains a separate,
explicitly-scoped future project.

## Success criteria
- The 6 sheet components carry Buy route + an orderpoint whose MIN reflects live
  open-MO demand (in the product's UoM; yield-converted where needed).
- Confirming a cabinet MO that raises demand above on-hand causes the native
  scheduler to draft an RFQ sized in purchase units — verified in test and spot-checked live.
- Zero change to MO component lines, stock moves, valuation, or existing tests.
