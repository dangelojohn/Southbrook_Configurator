---
course: 17
chapter: 17.15
title: Planning — Approve the MPS and Push to MRP
duration: 2
audience: Production planner closing the weekly MPS cycle
jtbd: approve the mps and push to mrp
department: Production Planning
custom_modules: southbrook_mes_mps
---

# Planning — Approve the MPS and Push to MRP

## When you use this

You ran the 13-week generator (lesson 17.14), reviewed the gaps, and now
want to commit the plan and have native MRP create the replenishment MOs.

## The flow

1. **MES → MPS Workbench**, switch to list view.
2. **Filter `state = draft`.** Hide the executed historical rows.
3. **Multi-select** the rows you want to approve.
4. **Action → Approve.** State → `approved`. Each approved row's
   `to_supply_qty` gets registered as a demand record on the product's
   `procurement.group`.
5. **Run MRP.** *Inventory → Operations → Run Scheduler* (native). MRP
   consumes the demands and drafts the corresponding MOs / POs.

## What approval changes

- `state` → `approved` (locked for further edit by planner role)
- A procurement record is dispatched per row, qty = `to_supply_qty`
- Audit log entry on the chatter

## What approval does NOT do

- Does NOT confirm MOs (still draft after MRP creates them)
- Does NOT release work orders to the floor
- Does NOT update forecast (next week's generator pass re-reads forecast)

## Bulk approve safety

If you select 200 rows and 3 are wrong, *Reject* on those 3 before
clicking Approve. Once `executed`, only sysadmin can roll back.

## Common gotchas

- **MOs appear but qty looks wrong** — MRP rounded by `uom.rounding`;
  if the MPS asked for 7 and rounding=2, MRP makes 8.
- **PO didn't appear for purchased components** — supplier wasn't on the
  product. Add at *Inventory → Products → Purchase tab*.

## Deep dive

→ Course 2 lessons 2.3 *Bottleneck Scheduling* + 2.4 *Premium Orchestration Crons*
