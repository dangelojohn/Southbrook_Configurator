# Southbrook Materials — MRP

Density → weight and tiered cost sourcing on native MRP BoM/MO, plus (Phase-2)
a procurement **assist** layer.

## Weight (Phase-1 + geometry writeback)

Each `mrp.bom.line` resolves its component to a `southbrook.kitchen.material`
(`material_id`) and computes `component_volume_mm3` / `component_weight_kg` from
the cabinet's stored geometry (`_panel_volume_mm3` → carcass panel sum, material
`thickness_mm` override on box panels) and the material's `effective_density`,
using the LOCKED conversion `density(g/cm³) × volume_mm³ / 1e6`, HALF-UP 2 dp.
`material_weight_total` rolls this up per BoM / MO. Volume is attributed across
same-material sibling lines by `product_qty` share so a BoM counts its carcass
exactly once. Honesty contract: **0.0, never fabricated**, when geometry is
absent.

## Procurement assist (Phase-2)

Turns real consumption into a transparent *suggested order quantity*. It computes
decision numbers and configures native procurement — it **never creates or
confirms a purchase order** (assist-only).

- **`mrp.bom.line.material_demand_qty`** — how much of the component this BoM
  consumes, in the material's canonical demand unit: **m²** for sheet/area goods
  (`density_volume`/`density_area`), **linear m** for edgebanding
  (`linear_density`), **units** for hardware (`per_unit`/`none`, straight
  `product_qty` pass-through). Reuses the geometry→volume pipeline; the native
  BoM `product_qty` is left untouched. 0.0 when geometry is genuinely absent.
- **`product.supplierinfo.uom_yield_qty`** — net-new vendor data: how much
  material (in that canonical unit) one purchase unit yields (e.g. ~2.97 m² per
  4′×8′ sheet).
- **Waste** — `southbrook.kitchen.material._effective_waste_pct()` (material
  `waste_pct` override → nearest ancestor `material.family.default_waste_pct` →
  0). Structural cutting loss, applied *before* the round-up; kept separate from
  the operational `mrp.production.scrap_factor`.
- **`mrp.bom.line.suggested_purchase_qty`** (+ `suggested_purchase_uom_id`) —
  `CEIL( material_demand_qty × (1 + waste%) ÷ uom_yield_qty )` in the vendor's
  purchase unit (ceiling round-up uniformly — never buy a fraction of a unit).
  0 when demand, yield, or a vendor is missing (no fabricated suggestion).
- **Set Buy Route** button on material-linked products —
  `product.template.action_sb_set_route_buy()` adds the native Buy route so the
  native scheduler can procure them. Idempotent; creates no PO.

### Boundary (deferred to Phase-2b)

Orderpoint min/max automation, native scheduler end-to-end RFQ generation,
auto-confirm-below-threshold, `uom.uom` conversion into arbitrary purchase UoMs,
and actual-vs-estimate variance reconciliation are **not** in this increment —
this ships the decision numbers and the Buy-route config; a buyer drives the
native RFQ.

## Cutlist precision (2026-07-26)

Per-BoM-line material demand/weight is now **exact per panel** where resolvable,
falling back to the estimation-grade carcass share otherwise.

- `sb.panel.role` (in `sb_material_core`) — the seven cabinet panel roles
  (`side_L, side_R, top, bottom, back, shelf, door`). These codes match the
  panel-dict keys `mrp.bom._compute_panel_dimensions` returns, which the
  exact-volume code consumes directly — **not** identical to
  `sb.cutlist.PANEL_NAMES` (southbrook_kitchen_mrp), which uses
  `adjustable_shelf`, not `shelf` (I-3, final review, 2026-07-26).
  Converging with `sb.cutlist` later requires an explicit
  `shelf`<->`adjustable_shelf` mapping, not a bare code match.
- `southbrook.kitchen.material.panel_role_ids` — the roles a material makes
  (curated once per material). Seeded on the standard materials (carcass sheet
  goods → box roles; ¼″ ply / hardboard → back).
- A BoM line's demand/weight is **exact** when its material *uniquely owns* a
  role on that BoM (claimed by exactly one material): the line gets the summed
  `L×W×th` of exactly those panels; several lines of the same material split
  that material's panels by `product_qty`. `back` and `door` are first-class
  (previously cut-constant / excluded).
- `mrp.bom.line.material_demand_is_exact` (shown on the BoM line) — True when
  the exact per-role path was used, False when it fell back to the estimate.
- **Honesty:** when ownership is ambiguous (two materials claim a role) or the
  material has no roles or geometry is absent, the line keeps today's
  `_sb_component_share_volume_mm3` estimate — never fabricated.
- Note on area vs weight: sheet **area** demand is thickness-independent (a
  panel's face area is the same at any thickness); **weight** remains
  thickness-driven via the locked density×volume conversion.

**Deferred:** converging the post-MO `sb.cutlist` onto this role link;
`density_area` mapping; nesting/offcut optimization.

## Procurement loop (Phase-2b, 2026-07-26)

Native-procurement wiring on top of the Phase-2a assist. **Fork-1 (unchanged):** the native BoM-line `product_qty` is left untouched (=1 for continuous families) — the per-MO raw-material move stays size-blind by design; the material-aware `material_demand_qty` never writes into it. That split is closed one level up, at the orderpoint, by the size-aware trigger below (2026-07-27) rather than by touching `product_qty` itself.

- **UoM conversion helper** (`_sb_convert_demand_qty` / `_sb_demand_qty_in_uom`) — converts canonical demand (m²/lm) into a vendor's purchase UoM via native `uom.uom._compute_quantity`, but ONLY when the units share a reference (`_has_common_reference`); otherwise returns the value unchanged with a not-convertible flag (honest, never a wrong-unit number). This is the code path for when there's no `uom_yield_qty`; when a vendor yield IS recorded, the Phase-2a `suggested_purchase_qty` (sheets/rolls) is used instead.
- **Orderpoint MIN+MAX sync** (`action_sb_sync_orderpoints`, `action_sb_sync_orderpoint_max` kept as a delegating backcompat alias) — creates/updates `stock.warehouse.orderpoint` per material component per warehouse from a single open-MO demand rollup (`confirmed/progress/to_close`): **MIN = the converted demand itself; MAX = its CEIL, clamped ≥ MIN.** Idempotent (create-or-update by product/location/company). Honesty unchanged: skips (leaves any existing orderpoint's MIN/MAX untouched) when the demand can't be honestly expressed in the product's own UoM. Native records only — no bespoke reorder engine.
- **Native scheduler → draft RFQ** — with `route=Buy` (Phase-2a `action_sb_set_route_buy`) + orderpoints, native `stock.rule.run_scheduler` drafts the RFQ. Proven by test; **zero PO-creation code** of ours.
- **PO-line assist note** — read-only, non-stored computed fields on `purchase.order.line` (+ a Materials tab) showing the material-aware suggestion ("needs 3.2 sheets → order 4, incl 12% waste") or an honest "no vendor yield recorded" when data is absent. Never writes qty, never confirms.
- **Auto-confirm-below-threshold** (`res.company` toggle, **default OFF**) — the ONLY `button_confirm()` call site. Double-gated: setting ON **and** `0 < amount_total ≤ threshold`. Hooks `stock.rule._run_buy` calling `super()` first/unchanged, then optionally confirms an already-native-created draft PO; every auto-confirm is logged. When off, behavior is byte-identical to native.

**Live-data dependency:** the PO-line suggestion is actionable only once vendors have `uom_yield_qty` (the yield worksheet — shop data). All behavior is testable with synthetic data.

## Size-aware procurement trigger (Fork-1 Option C, 2026-07-27)

Closes the gap noted above: previously, `action_sb_sync_orderpoint_max` only wrote **MAX** (the ceiling on how much to reorder up to); **MIN never touched** meant the native reorder *trigger* itself (`qty_forecast < product_min_qty`) never engaged with real demand at all — a component could sit with zero orderpoint activity no matter how much open-MO demand existed. `action_sb_sync_orderpoints` (see above) now sets **MIN = that same demand rollup**, so the native scheduler's trigger genuinely fires off real material demand, not just a human-configured or absent MIN.

- **Activation migration** — `migrations/19.0.1.14.0/post-migrate.py` applies `action_sb_set_route_buy()` + `action_sb_sync_orderpoints()` to the 6 live sheet components (by `default_code`: `RM-MELAMINE_WHITE_5_8`, `SBK-SHEET-MB34-WW`, `RM-PLY_3_4`, `SBK-SHEET-BPY12`, `SBK-SHEET-BPY14`, `RM-HARDBOARD_1_4`). Idempotent; skips (logs, never errors) any code absent from a given database.
- **Fork-1 / `product_qty` still untouched** — the native BoM-line `product_qty` and the MO raw-material move stay exactly as `product_configurator_mrp` writes them (qty=1 per component); this closure is entirely at the orderpoint layer, one level removed from consumption.
- **Option A ("true consumption & valuation") remains deferred** — a separate, explicitly-scoped future project; out of this increment.
- **Proof:** `tests/test_scheduler_draft_rfq.py::test_min_from_demand_triggers_draft_rfq_end_to_end` — confirmed open MO → `action_sb_sync_orderpoints()` (no hand-set MIN) → `product_min_qty > 0` → native `stock.rule.run_scheduler` → draft `purchase.order` for the component, sized in purchase units. On-hand is 0 in the fixture, so `forecast(0) < min` fires the trigger exactly as it will live once the migration activates the 6 real components.
