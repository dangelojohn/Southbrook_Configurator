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
