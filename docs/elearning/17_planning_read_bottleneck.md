---
course: 17
chapter: 17.17
title: Planning — Read the Bottleneck Report and Act
duration: 3
audience: Production planner doing the morning floor-load check
jtbd: read the bottleneck report and act
department: Production Planning
custom_modules: southbrook_mes_mps, southbrook_premium_orchestration
---

# Planning — Read the Bottleneck Report and Act

## When you use this

Daily, around 7:30 AM. The bottleneck report tells you which workcenter
will hit capacity first this week so you can pre-empt the queue rather
than react to it.

## Where this lives

Two views worth knowing:

- **MES → Bottleneck Report** — pure-MPS view, runs over the rolling 13
  weeks, lists workcenters by `utilisation_pct = demand_hours /
  capacity_hours`
- **Kitchen Ops → Workcenter Bottleneck** — operational view, runs over
  THIS week and the next, uses live MO state + downtime logs

## Reading the report

- **Green:** `utilisation_pct < 80%`. Healthy.
- **Amber:** `80% ≤ utilisation_pct < 100%`. Plan to add overtime,
  reroute, or push dates.
- **Red:** `utilisation_pct ≥ 100%`. You're overcommitted. Choose: ship
  late, decline orders, reroute, or run a second shift.

## The 3 actions

1. **Reroute.** If the MO has a parallel-capable workcenter
   (SB-CNC-BORE ↔ CNC02 backup), open the work order and switch
   workcenter_id. Lesson 17.16 explains the constraint.
2. **Extend shift.** *Kitchen Ops → Workcenter Bottleneck* → row action →
   *Add Overtime Block*. Adds an `mrp.workcenter.productivity` allowance
   for the period.
3. **Defer SO promise.** If neither works, push the customer's promise
   date and post a Hermes-driven notification (CS will catch it on their
   queue).

## Common gotchas

- **Utilisation looks fine but you're missing dates** — utilisation is
  weekly avg; spikes within the week can still miss. Open the daily
  breakdown.
- **`capacity_hours` is wrong** — workcenter's `time_efficiency` and
  `oee_target` drive it. Stale values give bogus utilisation.

## Deep dive

→ Course 3 lesson 3.3 *OEE per Workcenter*
→ Course 12 lesson 12.5 *Floor Load Dashboards*
