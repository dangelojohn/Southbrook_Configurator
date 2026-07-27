---
course: 17
chapter: 17.35
title: Finance — Review WIP Before Close
duration: 2
audience: Controller doing month-end WIP reconciliation
jtbd: review wip before close
department: Finance / Accounting
custom_modules: southbrook_finance_pack
---

# Finance — Review WIP Before Close

## When you use this

Step 5 of the monthly close (lesson 17.32). Your GL has a WIP balance;
the operational reality is "these MOs are in progress." This lesson
reconciles them.

## Where this lives

**Finance → WIP Report** (`menu_finance_wip_report`).

## What the report shows

Rolls every MO with state `progress` or `confirmed` by:
- `mo_ref`, `product`, `cost_so_far`
- `cost_to_complete`
- `wip_value = cost_so_far`

Group by `responsible_team` to see where the WIP lives (Cutting, Edge,
Assembly, Finishing).

## The reconciliation

- **WIP report total** = sum of all open MO costs
- **GL WIP account balance** = closing balance of `211000-WIP` (or your
  chart's equivalent)
- **Variance** = report - GL

If variance > $1, investigate:

- An MO marked `done` but consumption not posted → GL says lower than
  report
- An MO with backdated consumption → GL says higher than report
- A scrapped cabinet not journalled → either direction depending on which
  side did the cleanup

## Drilling into a variance

Click into the suspect MO from the report. The cost breakdown shows:
- Material consumed (from `stock.move`)
- Labour applied (from `mrp.workorder.duration_done`)
- Overhead (from `mrp.workcenter.cost_per_hour` × duration)

Cross-check each against the GL journal entries on the MO.

## Common gotchas

- **Variance equals exactly one MO's cost** — that MO either completed
  on the last day of the period and didn't get journalled, or vice versa.
- **WIP report is empty but MOs are open** — the `state` filter excludes
  drafts. Drafts shouldn't have WIP value either, so that's correct.

## Deep dive

→ Course 19 (Finance Pack — to be authored)
