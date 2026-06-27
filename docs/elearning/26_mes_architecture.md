---
course: 26
chapter: 26.1
title: MES + MPS Module — Architecture
duration: 7
audience: Developer or admin learning southbrook_mes_mps internals
prereqs: Native Odoo MRP + Manufacturing familiarity
custom_modules: southbrook_mes_mps
---

# MES + MPS Module — Architecture

## The module at a glance

- Path: `addons/southbrook_mes_mps/`
- Version: 19.0.1.0.0
- Depends on: `base`, `mail`, `mrp`, `product`,
  `southbrook_manufacturing_intelligence`

## Source layout

```
addons/southbrook_mes_mps/
├── models/
│   ├── mps_period.py         — rolling 13-week MPS records
│   ├── workcenter_capacity.py — calculated capacity per workcenter per week
│   ├── oee_snapshot.py        — daily OEE per workcenter
│   ├── bottleneck_report.py   — read-only aggregated view
│   └── mi_engine_ext.py
├── views/
└── data/
```

## What MES vs MPS

- **MES** (Manufacturing Execution System) — operates the shop
  floor today. OEE, breakdowns, in-progress tracking.
- **MPS** (Master Production Schedule) — plans the next 13 weeks.
  Demand × capacity = production plan.

This module covers both. The MPS part schedules; the MES part
monitors execution.

## Install

```bash
./scripts/deploy_to_qnap.sh southbrook_mes_mps
```

What -i does:
1. Creates mps_period, workcenter_capacity, oee_snapshot tables
2. Creates the SQL view for bottleneck_report
3. Adds 5 menus under MES
4. Registers crons (capacity recompute, OEE rollup, MPS expiry)

## Cron landscape

| Cron | Schedule | Purpose |
|---|---|---|
| `cron_capacity_recompute` | weekly Mondays 02:00 | Recomputes 13-week capacity per workcenter |
| `cron_oee_rollup` | daily 23:30 | Aggregates today's productivity into OEE snapshot |
| `cron_mps_expiry` | weekly Mondays 03:00 | Marks periods past their week as `executed` |

## Key models

### MPS Period

```python
class SouthbrookMesMpsMpsPeriod(models.Model):
    _name = "southbrook.mes_mps.mps_period"
```

One row per product per week_start. State machine:
draft → approved → executed.

### Workcenter Capacity

```python
class SouthbrookMesMpsWorkcenterCapacity(models.Model):
    _name = "southbrook.mes_mps.workcenter_capacity"
```

Computed weekly: `hours_per_shift × shifts × days_per_week × time_efficiency`.

### OEE Snapshot

```python
class SouthbrookMesMpsOeeSnapshot(models.Model):
    _name = "southbrook.mes_mps.oee_snapshot"
```

One row per workcenter per day. Stored A × P × Q with breakdown.

### Bottleneck Report

```python
class SouthbrookMesMpsBottleneckReport(models.Model):
    _name = "southbrook.mes_mps.bottleneck_report"
    _auto = False  # SQL view
```

Live view over capacity + demand.

## Common mistakes + how to recover

- **"MPS Workbench empty"** — no periods generated yet. Run
  `Generate Rolling 13 Weeks` server action on selected products.
- **"OEE snapshots missing yesterday"** — cron didn't run.
  Manual trigger from server actions.
- **"Bottleneck report stale"** — SQL view query. Should be live;
  if showing old data, verify `auto = False` materialised correctly.

## Quiz

**Q1.** MES vs MPS — what each covers?

> MES = execution + monitoring (OEE, breakdowns). MPS = planning
> (13-week schedule, capacity allocation).

**Q2.** OEE snapshot model — granularity?

> Per workcenter per day. Stored values for fast historical
> queries; cron-populated.

**Q3.** When does MPS period state advance to `executed`?

> Weekly Monday 03:00 cron marks periods whose `week_start` is in
> the past. So Monday morning, last week's periods are executed.

**Q4.** Workcenter capacity recompute interval?

> Weekly. The numbers change rarely (shift count, days/week);
> daily compute would waste cycles.

**Q5.** Adding a 14th week of MPS — approach?

> The rolling 13-week generator handles this. Each week's run
> adds the new week 13 weeks out + the prior week-1 ages out.
