---
course: 26
chapter: 26.5
title: MES + MPS Module — Bottleneck Report Query
duration: 6
audience: Developer working on bottleneck logic
prereqs: Lessons 26.1, 26.3
custom_modules: southbrook_mes_mps
---

# MES + MPS Module — Bottleneck Report Query

## The model

```python
class SouthbrookMesMpsBottleneckReport(models.Model):
    _name = "southbrook.mes_mps.bottleneck_report"
    _auto = False  # SQL view
```

Fields (from the view):

```python
workcenter_id      = fields.Many2one("mrp.workcenter", readonly=True)
week_start         = fields.Date(readonly=True)
capacity_hours     = fields.Float(readonly=True)
demand_hours       = fields.Float(readonly=True)
utilisation_pct    = fields.Float(readonly=True)
```

## SQL view

```sql
CREATE OR REPLACE VIEW southbrook_mes_mps_bottleneck_report AS
SELECT
    ROW_NUMBER() OVER () AS id,
    c.workcenter_id,
    c.week_start,
    c.effective_capacity_hours AS capacity_hours,
    COALESCE(SUM(
        wo.duration_expected
    ) / 60.0, 0) AS demand_hours,
    CASE 
        WHEN c.effective_capacity_hours > 0 THEN
            COALESCE(SUM(wo.duration_expected) / 60.0, 0) / 
            c.effective_capacity_hours * 100
        ELSE 0
    END AS utilisation_pct
FROM southbrook_mes_mps_workcenter_capacity c
LEFT JOIN mrp_workorder wo ON wo.workcenter_id = c.workcenter_id
    AND wo.date_planned_start >= c.week_start
    AND wo.date_planned_start < c.week_start + INTERVAL '7 days'
    AND wo.state IN ('ready', 'progress')
GROUP BY c.id, c.workcenter_id, c.week_start, c.effective_capacity_hours;
```

## Decoration rules (in view)

```xml
<list decoration-success="utilisation_pct &lt; 80"
      decoration-warning="utilisation_pct &gt;= 80 and utilisation_pct &lt; 100"
      decoration-danger="utilisation_pct &gt;= 100">
    <field name="workcenter_id"/>
    <field name="week_start"/>
    <field name="capacity_hours"/>
    <field name="demand_hours"/>
    <field name="utilisation_pct"/>
</list>
```

## Pivot view

```xml
<pivot string="Bottleneck Pivot">
    <field name="workcenter_id" type="row"/>
    <field name="week_start" type="col" interval="week"/>
    <field name="utilisation_pct" type="measure"/>
</pivot>
```

Easy scan: rows are workcenters, cols are weeks, cells are
utilisation percentages. Red cells jump out.

## Common queries

### "Show me red workcenters this week"

```python
self.env["southbrook.mes_mps.bottleneck_report"].search([
    ("week_start", "=", today_monday),
    ("utilisation_pct", ">=", 100),
])
```

### "Show me workcenters that have been red 3+ weeks running"

```python
# More complex — needs aggregation
self.env.cr.execute("""
    SELECT workcenter_id, COUNT(*) AS red_weeks
    FROM southbrook_mes_mps_bottleneck_report
    WHERE utilisation_pct >= 100
      AND week_start >= %s
    GROUP BY workcenter_id
    HAVING COUNT(*) >= 3
""", (today - relativedelta(weeks=4),))
```

## Common mistakes + how to recover

- **"Utilisation > 200%"** — `duration_expected` may be inflated.
  Verify the work orders are correctly estimated.
- **"Workcenter shows 0 demand"** — no work orders scheduled OR
  filter mismatch on state. Check.
- **"Pivot view too dense"** — filter to one product family or
  one workcenter type first.

## Quiz

**Q1.** Why SQL view instead of stored model?

> Live computation; data fully derived. No business reason for a
> separate table.

**Q2.** Demand hours from `mrp.workorder.duration_expected`.
What if work orders have wrong estimates?

> Bottleneck shows wrong utilisation. Fix the estimates first.

**Q3.** Workcenter with 60% utilisation 5 weeks running. Action?

> Underutilised — could absorb more demand. Sales conversation,
> or accept the spare capacity for resilience.

**Q4.** Same workcenter at 60% but next week at 110%. Action?

> Spike in demand. Reroute to backup workcenter (if available),
> push dates, or add overtime block.

**Q5.** Filter to "red workcenters this month." Approach?

> Search domain: `[("utilisation_pct", ">=", 100), ("week_start",
> ">=", month_start), ("week_start", "<=", month_end)]`.
