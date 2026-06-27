---
course: 27
chapter: 27.3
title: CMMS + WMS Module — MTBF and MTTR Math
duration: 8
audience: Developer working on capability metrics
prereqs: Lesson 27.1
custom_modules: southbrook_cmms_wms
---

# CMMS + WMS Module — MTBF and MTTR Math

## The model

```python
class SouthbrookCmmsMtbfMttrReport(models.Model):
    _name = "southbrook.cmms.mtbf_mttr_report"
    _description = "MTBF / MTTR Capability Report"
```

Fields:

```python
name              = fields.Char()
equipment_id      = fields.Many2one("maintenance.equipment",
                                    required=True)
as_of_date        = fields.Date(default=fields.Date.today)
period_days       = fields.Integer(default=90)

breakdown_count       = fields.Integer(readonly=True)
total_downtime_hours  = fields.Float(readonly=True)
total_runtime_hours   = fields.Float(readonly=True)
mtbf_hours            = fields.Float(readonly=True)
mttr_hours            = fields.Float(readonly=True)
availability_pct      = fields.Float(readonly=True)
```

## The math

```python
def action_compute(self):
    self.ensure_one()
    period_start = self.as_of_date - relativedelta(days=self.period_days)
    
    breakdowns = self.env["southbrook.cmms.breakdown_alert"].search([
        ("equipment_id", "=", self.equipment_id.id),
        ("state", "=", "fixed"),
        ("reported_at", ">=", period_start),
        ("reported_at", "<=", self.as_of_date),
    ])
    
    count = len(breakdowns)
    downtime_hours = sum(b.total_downtime_min for b in breakdowns) / 60
    
    # Runtime = total hours in period - downtime
    period_hours = self.period_days * 24
    runtime_hours = period_hours - downtime_hours
    
    self.write({
        "breakdown_count": count,
        "total_downtime_hours": downtime_hours,
        "total_runtime_hours": runtime_hours,
        "mtbf_hours": runtime_hours / count if count else 0,
        "mttr_hours": downtime_hours / count if count else 0,
        "availability_pct": (runtime_hours / period_hours * 100)
                            if period_hours else 0,
    })
```

## Reading the metrics

### MTBF — Mean Time Between Failures
Higher = better. Tells you how long the equipment runs without breaking.

### MTTR — Mean Time To Repair
Lower = better. Tells you how fast maintenance fixes breakdowns.

### Availability %
The composite headline. > 95% = healthy, < 80% = concerning.

## Period choice

Default 90 days. Trade-off:
- **Shorter** (30 days): more responsive to recent changes,
  but noisy
- **Longer** (180 days): smooth trend but lags real-time

For equipment with 1-2 breakdowns/month, 90 days gives ~3-6
data points — workable. Smaller equipment count needs longer period.

## Daily cron

```python
@api.model
def _cron_compute_mtbf_mttr(self):
    """Refresh MTBF/MTTR for all active equipment."""
    today = fields.Date.today()
    for equipment in self.env["maintenance.equipment"].search([
        ("active", "=", True),
    ]):
        report = self.search([
            ("equipment_id", "=", equipment.id),
            ("as_of_date", "=", today),
        ], limit=1)
        if not report:
            report = self.create({
                "equipment_id": equipment.id,
                "as_of_date": today,
                "name": f"{equipment.name} - {today}",
            })
        report.action_compute()
```

## Historical trend

Each day's report stays as a row. Trend visible via graph view
filtered by equipment:

```python
# Last 90 reports for one equipment = ~3 months of trend
self.search([
    ("equipment_id", "=", equipment_id),
], order="as_of_date desc", limit=90)
```

## Common mistakes + how to recover

- **"MTBF = 0"** — no closed breakdowns in period. Either
  legitimate (no breakdowns) or breakdowns weren't closed with
  downtime data.
- **"Availability > 100%"** — over-reported downtime negatives
  out. Audit recent close-outs.
- **"MTTR seems too low"** — downtime under-reported. Operators
  may close before maintenance finishes.

## Quiz

**Q1.** 90 days, 5 breakdowns, total 12 hours downtime. MTBF?

> Runtime = 90×24 - 12 = 2148 hours. MTBF = 2148 / 5 = **429.6 hours**.

**Q2.** Same data: MTTR?

> 12 / 5 = **2.4 hours per repair**.

**Q3.** Same data: availability?

> 2148 / 2160 × 100 = **99.4%**. Excellent.

**Q4.** Equipment with no breakdowns in 90 days. MTBF?

> Undefined (divide by zero); model returns 0. Interpret as
> "all 90 days uptime, no failures to measure between."

**Q5.** Equipment goes through periodic 8-hour PM (planned).
Does PM count as downtime?

> Currently no — only breakdown alerts (corrective) count.
> PM (preventive) is excluded. May want to include for full
> availability picture.
