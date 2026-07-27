---
course: 17
chapter: 17.16
title: Planning — Reschedule a Work Order After a Breakdown
duration: 3
audience: Production planner reacting to a workcenter breakdown
jtbd: reschedule a work order after a breakdown
department: Production Planning
custom_modules: southbrook_cmms_wms, southbrook_mrp_pm, southbrook_premium_orchestration
---

# Planning — Reschedule a Work Order After a Breakdown

## When you use this

A workcenter (SB-CNC-BORE, SB-EDGE, SB-ASSY, etc.) breaks down. The
maintenance lead has filed a breakdown alert. Now you need to move
in-progress + queued work to another workcenter or push the dates.

## What auto-happened

- Maintenance opened a `southbrook.cmms.breakdown_alert` (lesson 17.24)
- If they clicked *Block Affected MOs*, the alert created
  `mrp.production` blocks on every MO whose work order targets the broken
  workcenter
- The MI engine surfaced an *install-risk* tile (lesson 17.17 to read it)

## Your 3-step response

1. **Find the affected MOs.** *Kitchen Ops → Workcenter Bottleneck* shows
   the queue by workcenter; the broken one will spike.
2. **Decide: reroute or defer.** Some cabinets can run on the backup
   workcenter (SB-CNC-BORE → CNC02 backup; SB-DOOR → SB-ASSY in a pinch).
   Some can't (SAND / PAINT / CURE are unique).
3. **Reroute on the MO.** Open the affected MO → *Work Orders* tab →
   edit the `workcenter_id` on the affected work order. The MRP scheduler
   re-runs and the new dates flow downstream.

## Defer flow

If you can't reroute, push dates:

- Open the MO header → *Scheduled Start*. Bump by the maintenance ETA
  (visible on the breakdown alert).
- Hermes / Fabio will surface this as a *recommendation* (lesson 3.2) for
  the Plant GM to acknowledge.

## Common gotchas

- **Reroute disabled** — the new workcenter doesn't have the required
  `workcenter.capability` for that operation. The MO's bom_routing
  expects an edge_bander; only SB-EDGE has it.
- **Bulk reroute** — Action menu on the work order list view. Be careful;
  this doesn't validate capability for each row individually.

## Deep dive

→ Course 3 lesson 3.2 *Approving Hermes Recommendations*
→ Course 2 lesson 2.3 *Bottleneck Scheduling*
