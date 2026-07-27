---
course: 17
chapter: 17.14
title: Planning — Generate the Rolling 13-Week MPS
duration: 3
audience: Production planner doing the weekly MPS cycle
jtbd: generate the rolling 13-week mps
department: Production Planning
custom_modules: southbrook_mes_mps
---

# Planning — Generate the Rolling 13-Week MPS

## When you use this

The Monday-morning planning cycle. The MPS Workbench rolls forward by one
week each time; this lesson is the 3-minute "I just need to run it"
tutorial.

## Where this lives

**MES → MPS Workbench**

(Menu `menu_mps_workbench` from `southbrook_mes_mps`.)

## The flow

1. **Open the workbench.** Default view is the pivot — product × week_start,
   measures forecast_qty + to_supply_qty.
2. **Filter to your products.** The default groups by product; switch to a
   subset if you're planning one family.
3. **Select products → Action menu → *Generate Rolling 13 Weeks*.** This is
   the server action `action_mps_generate_13` bound to
   `product.model_product_product`. It creates / refreshes 13 weeks of
   `southbrook.mes_mps.mps_period` rows per selected product.
4. **Review.** The pivot now shows updated `forecast_qty`,
   `actual_demand_qty` (from confirmed SOs), `planned_supply_qty` (from
   confirmed MOs), and the computed `to_supply_qty` gap.

## Reading the workbench

- **Green row, `to_supply_qty = 0`** — supply meets demand, no action
  needed.
- **Amber row, `to_supply_qty > 0`** — need to push MOs / POs to cover the
  gap. Click the row to see the period detail.
- **`state = executed`** (green decoration on list view) — this period has
  shipped; data is historical, don't edit.

## Approve flow

For each draft `mps.period`, the *Approve* button changes state to
`approved` and feeds the next MRP run. Bulk-approve via list view, multi-
select + Action → Approve.

## Common gotchas

- **Generate ran but nothing appeared** — you probably ran it from the
  template view; the server action is bound to `product.product` (variant)
  not `product.template`. Try from the variant list.
- **`forecast_qty` is 0 across the board** — no forecast model is seeded.
  Manual entry until forecast-from-history lands as a v1.1 feature.

## Deep dive

→ Course 2 lesson 2.5 *Reading the MI Report*
→ Course 7 *MES + MPS Workbench* (module deep-dive when authored)
