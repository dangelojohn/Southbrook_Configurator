---
course: 26
chapter: 26.4
title: MES + MPS Module — OEE Snapshot Model
duration: 7
audience: Developer working on OEE compute or rollup
prereqs: Lesson 26.1
custom_modules: southbrook_mes_mps
---

# MES + MPS Module — OEE Snapshot Model

## The model

```python
class SouthbrookMesMpsOeeSnapshot(models.Model):
    _name = "southbrook.mes_mps.oee_snapshot"
```

Fields:

```python
workcenter_id    = fields.Many2one("mrp.workcenter", required=True)
snapshot_date    = fields.Date(required=True)

availability_pct = fields.Float()  # 0-100
performance_pct  = fields.Float()
quality_pct      = fields.Float()
oee_pct          = fields.Float(compute="_compute_oee", store=True)

planned_production_time_min = fields.Float()
actual_run_time_min         = fields.Float()
ideal_cycle_time_min        = fields.Float()
total_pieces                = fields.Float()
good_pieces                 = fields.Float()
```

## OEE formula

```python
@api.depends("availability_pct", "performance_pct", "quality_pct")
def _compute_oee(self):
    for s in self:
        s.oee_pct = (s.availability_pct *
                     s.performance_pct *
                     s.quality_pct) / 10000
```

Multiplicative, divided by 10000 because each factor is 0-100.

## Daily rollup cron

```python
@api.model
def _cron_rollup_oee(self):
    """Daily 23:30: snapshot today's OEE per workcenter."""
    today = fields.Date.today()
    
    for wc in self.env["mrp.workcenter"].search([("active", "=", True)]):
        snapshot_data = self._compute_workcenter_oee(wc, today)
        
        existing = self.search([
            ("workcenter_id", "=", wc.id),
            ("snapshot_date", "=", today),
        ])
        if existing:
            existing.write(snapshot_data)
        else:
            self.create({
                "workcenter_id": wc.id,
                "snapshot_date": today,
                **snapshot_data,
            })
```

## Per-workcenter OEE compute

```python
def _compute_workcenter_oee(self, workcenter, target_date):
    """Compute A × P × Q for the workcenter on the date."""
    productivity_records = self.env["mrp.workcenter.productivity"].search([
        ("workcenter_id", "=", workcenter.id),
        ("date_start", ">=", target_date),
        ("date_start", "<", target_date + timedelta(days=1)),
    ])
    
    planned_time = workcenter.hours_per_shift * 60 * \
                   workcenter.shifts_per_day  # minutes
    
    productive_time = sum(
        (r.date_end - r.date_start).total_seconds() / 60
        for r in productivity_records.filtered(
            lambda r: r.loss_id.loss_type == "productive"))
    
    breakdown_time = sum(
        (r.date_end - r.date_start).total_seconds() / 60
        for r in productivity_records.filtered(
            lambda r: r.loss_id.loss_type == "availability"))
    
    availability = (productive_time / (productive_time + breakdown_time)) \
                   if (productive_time + breakdown_time) else 0
    
    # Performance: actual output vs ideal
    workorders = self.env["mrp.workorder"].search([
        ("workcenter_id", "=", workcenter.id),
        ("date_end", ">=", target_date),
        ("date_end", "<", target_date + timedelta(days=1)),
        ("state", "=", "done"),
    ])
    
    total_pieces = sum(workorders.mapped("qty_produced"))
    ideal_cycle = workcenter.time_per_cycle  # min/piece
    ideal_time = total_pieces * ideal_cycle
    performance = ideal_time / productive_time if productive_time else 0
    
    # Quality: good vs total
    good_pieces = sum(workorders.mapped("qty_produced")) - \
                  sum(workorders.mapped("scrap_qty"))
    quality = good_pieces / total_pieces if total_pieces else 0
    
    return {
        "availability_pct": availability * 100,
        "performance_pct": performance * 100,
        "quality_pct": quality * 100,
        "planned_production_time_min": planned_time,
        "actual_run_time_min": productive_time,
        "ideal_cycle_time_min": ideal_cycle,
        "total_pieces": total_pieces,
        "good_pieces": good_pieces,
    }
```

## Historical trend

Snapshots accumulate; trends visible via list/graph view.

```python
# Last 30 days OEE trend for a workcenter
self.env["southbrook.mes_mps.oee_snapshot"].search([
    ("workcenter_id", "=", wc_id),
    ("snapshot_date", ">", fields.Date.today() - relativedelta(days=30)),
]).read(["snapshot_date", "oee_pct"])
```

## Common mistakes + how to recover

- **"OEE = 0 for all workcenters yesterday"** — cron didn't run.
  Manual: trigger server action *Rollup Yesterday*.
- **"Performance > 100%"** — operator beat ideal cycle time. Real;
  flag for ideal_cycle review (may be too conservative).
- **"Quality = 0% for some workcenters"** — no work orders
  completed that day. Expected if workcenter idle.

## Quiz

**Q1.** OEE formula?

> A × P × Q. Each factor 0-100; result 0-100. Multiplicative.

**Q2.** Workcenter Availability 80, Performance 90, Quality 95.
OEE?

> (80 × 90 × 95) / 10000 = **68.4%**.

**Q3.** Performance = 105%. Issue?

> Not necessarily an issue — operator beat ideal cycle. May indicate
> the ideal cycle time is too conservative. Flag for review.

**Q4.** Daily rollup runs 23:30. What about partial days
(today's not done yet)?

> Snapshot for today is taken at 23:30. Live data during the day
> not snapshotted; query the live productivity records directly.

**Q5.** Adding a new loss reason to mrp.workcenter.productivity.
Effect?

> Categorise it via `loss_id.loss_type` (availability vs
> performance vs quality). OEE compute reads `loss_type` for
> bucketing.
