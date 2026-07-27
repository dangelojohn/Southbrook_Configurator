---
course: 17
chapter: 17.27
title: Maintenance — View MTBF/MTTR for an Asset
duration: 2
audience: Maintenance lead or Plant GM checking equipment health
jtbd: view mtbf mttr for an asset
department: Maintenance
custom_modules: southbrook_cmms_wms
---

# Maintenance — View MTBF/MTTR for an Asset

## When you use this

Monthly or before a capex review. You want to know which assets are
costing you in unplanned downtime.

## Where this lives

**CMMS → MTBF/MTTR Reports** (`menu_southbrook_cmms_mtbf_mttr_report`).

## Reading the list

Decorations on the list view (per
`addons/southbrook_cmms_wms/views/mtbf_mttr_report_views.xml`):
- **Green** — `availability_pct ≥ 95%` — healthy
- **Amber** — `80% ≤ availability_pct < 95%` — watch
- **Red** — `availability_pct < 80%` — investigate

Key columns:
- `mtbf_hours` — mean time between failures (higher = better)
- `mttr_hours` — mean time to repair (lower = better)
- `period_days` — over what window the math runs (default 90)

## Generate a fresh report

Form view → *Recompute* button. Runs the calc over the period for the
selected equipment. Bulk: list view multi-select + Action → Recompute.

## Graph view

Bar chart of MTBF by equipment. Quickly spots the worst offender.

## Common gotchas

- **MTBF shows 0** — no closed breakdowns in the period, OR breakdowns
  weren't logged with downtime (lesson 17.26 gotcha). Spot-check the
  count column.
- **Availability ≥ 100%** — a fluke in the math when downtime was over-
  reported. Audit the recent close-outs.

## Deep dive

→ Course 12 lesson 12.6 *MI Engine Observability*
