---
course: 26
chapter: 26.3
title: MES + MPS Module — Workcenter Capacity Calculation
duration: 7
audience: Developer working on capacity logic or bottleneck math
prereqs: Lessons 26.1, 26.2
custom_modules: southbrook_mes_mps
---

# MES + MPS Module — Workcenter Capacity Calculation

## The model

```python
class SouthbrookMesMpsWorkcenterCapacity(models.Model):
    _name = "southbrook.mes_mps.workcenter_capacity"
```

Fields:

```python
workcenter_id    = fields.Many2one("mrp.workcenter", required=True)
week_start       = fields.Date(required=True)
year             = fields.Integer(compute=..., store=True)
week_number      = fields.Integer(compute=..., store=True)

raw_capacity_hours    = fields.Float()  # before efficiency
effective_capacity_hours = fields.Float()  # after time_efficiency
oee_target            = fields.Float(default=0.85)
expected_output_units = fields.Float()
```

## Compute logic

```python
@api.model
def _cron_recompute_capacity(self):
    """Weekly: recompute next 13 weeks of capacity per workcenter."""
    today = fields.Date.today()
    current_monday = today - timedelta(days=today.weekday())
    
    for wc in self.env["mrp.workcenter"].search([]):
        for offset in range(13):
            week_start = current_monday + timedelta(weeks=offset)
            existing = self.search([
                ("workcenter_id", "=", wc.id),
                ("week_start", "=", week_start),
            ])
            if existing:
                existing.unlink()  # Recompute from scratch
            
            raw = wc.hours_per_shift * wc.shifts_per_day * 5  # 5-day week
            efficient = raw * (wc.time_efficiency or 1.0)
            expected = efficient * wc.oee_target / wc.time_per_cycle
            
            self.create({
                "workcenter_id": wc.id,
                "week_start": week_start,
                "raw_capacity_hours": raw,
                "effective_capacity_hours": efficient,
                "expected_output_units": expected,
            })
```

## Time efficiency vs OEE

Two related but different concepts:

- **`time_efficiency`** (set on workcenter) — wall-clock to working
  time ratio. Accounts for setup, breaks, idle. Default 0.9.
- **`oee_target`** — quality-aware effectiveness. Default 0.85 =
  85% (typical for cabinet shops).

So raw 40h × 0.9 efficiency = 36 effective hours. Then × 0.85 OEE
target = 30.6 expected productive hours.

## Holidays + planned downtime

The current implementation uses 5 days/week flat. Holidays not
considered. v1.1 candidate: integrate
`resource.calendar.leaves` to subtract holidays + planned PM.

For now, manually adjust capacity rows for known downtime:

```python
def adjust_for_pm(self, workcenter_id, pm_start, pm_end, hours):
    """Subtract planned maintenance hours from capacity."""
    affected = self.search([
        ("workcenter_id", "=", workcenter_id),
        ("week_start", ">=", pm_start),
        ("week_start", "<=", pm_end),
    ])
    for cap in affected:
        cap.raw_capacity_hours -= hours
        # Recompute downstream
```

## Common mistakes + how to recover

- **"Capacity hours look wrong"** — verify workcenter's
  `hours_per_shift` + `shifts_per_day`. Default values may not
  match reality.
- **"Effective != raw × time_efficiency"** — possible recompute
  bug; check the cron's last execution.
- **"Holidays not accounted for"** — known limitation.
  Manually adjust.

## Quiz

**Q1.** Workcenter 8 hours/shift, 2 shifts/day, 5 days/week.
time_efficiency = 0.9. Effective hours?

> 8 × 2 × 5 × 0.9 = **72 hours**.

**Q2.** Raw 40h × 0.9 efficiency × 0.85 OEE × 1/0.5 cycle =?

> 40 × 0.9 × 0.85 / 0.5 = **61.2 expected output units**.

**Q3.** Capacity recompute runs weekly. Why not daily?

> Underlying workcenter data changes rarely. Daily recompute
> wastes cycles.

**Q4.** Holiday this week. Capacity rows show full hours. Effect?

> Bottleneck report shows too-rosy utilisation. Manually adjust
> via `adjust_for_pm` or accept the slight overestimate.

**Q5.** New workcenter added today. When is its first capacity
row?

> Next cron run (next Monday 02:00). Manual trigger available via
> server action.
