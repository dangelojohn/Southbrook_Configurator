---
course: 26
chapter: 26.6
title: MES + MPS Module — MI Engine Integration
duration: 6
audience: Developer working on MES/MPS signals to MI engine
prereqs: Lessons 26.1, 26.4, 26.5
custom_modules: southbrook_mes_mps, southbrook_manufacturing_intelligence
---

# MES + MPS Module — MI Engine Integration

## Signals MES surfaces

1. **Workcenter red (>100% utilisation)** — recommendation for planner
2. **OEE drop > 10% week-over-week** — recommendation for Plant GM
3. **MPS approval pending > 1 week** — recommendation for planner

## Hook

```python
class MiEngineMesExt(models.AbstractModel):
    _inherit = "southbrook.mi.engine"
    
    @api.model
    def _check_mes_signals(self):
        self._check_workcenter_red()
        self._check_oee_drop()
        self._check_mps_stale()
    
    def _check_workcenter_red(self):
        today_monday = self._this_monday()
        red = self.env["southbrook.mes_mps.bottleneck_report"].search([
            ("week_start", "=", today_monday),
            ("utilisation_pct", ">=", 100),
        ])
        for r in red:
            self._emit_recommendation(
                subject=f"Workcenter {r.workcenter_id.name} red "
                        f"({r.utilisation_pct:.0f}%)",
                body=f"Demand {r.demand_hours}h vs capacity "
                     f"{r.capacity_hours}h. Decide reroute / shift / "
                     f"date push.",
                affected_records=r.workcenter_id,
                persona="production_planner",
            )
    
    def _check_oee_drop(self):
        last_week = fields.Date.today() - relativedelta(days=7)
        for wc in self.env["mrp.workcenter"].search([]):
            recent = self.env["southbrook.mes_mps.oee_snapshot"].search([
                ("workcenter_id", "=", wc.id),
                ("snapshot_date", ">", last_week),
            ])
            prior = self.env["southbrook.mes_mps.oee_snapshot"].search([
                ("workcenter_id", "=", wc.id),
                ("snapshot_date", "<=", last_week),
                ("snapshot_date", ">", last_week - relativedelta(days=7)),
            ])
            if recent and prior:
                recent_avg = sum(r.oee_pct for r in recent) / len(recent)
                prior_avg = sum(p.oee_pct for p in prior) / len(prior)
                if (prior_avg - recent_avg) > 10:
                    self._emit_recommendation(
                        subject=f"{wc.name} OEE dropped "
                                f"{prior_avg-recent_avg:.1f}%",
                        body=f"Prior week avg {prior_avg:.1f}; "
                             f"this week avg {recent_avg:.1f}. "
                             f"Investigate.",
                        persona="mfg_manager",
                    )
```

## Wiring into MI loop

`southbrook.mi.engine._check_all` calls all `_check_*` methods:

```python
@api.model
def _check_all(self):
    """Main MI engine loop."""
    self._check_quality_signals()
    self._check_finance_signals()
    self._check_mes_signals()   # ← added by MES extension
    # ... etc.
```

## Dedup

Same dedup pattern as Finance (lesson 24.6):

```python
def _emit_recommendation(self, subject, ...):
    existing = self.env["hermes.recommendation"].search([
        ("subject", "=", subject),
        ("state", "=", "pending_review"),
        ("created_at", ">", fields.Datetime.now() - relativedelta(days=1)),
    ], limit=1)
    if existing:
        return existing
    return self.env["hermes.recommendation"].create({...})
```

## Common mistakes + how to recover

- **"Workcenter red rec fires every day"** — same workcenter,
  same week. Dedup by subject + week_start.
- **"OEE drop rec fires immediately on first day with data"** —
  missing the "prior week required" guard. Add.
- **"MPS stale rec — what's the threshold?"** — `> 7 days
  pending_approval`. Tune via system param.

## Quiz

**Q1.** Workcenter red 3 weeks running. Recommendations?

> One per week (dedup'd). Or via separate "chronic red" logic.

**Q2.** OEE drop signal — what triggers?

> > 10% drop in 7-day avg vs prior 7-day avg.

**Q3.** OEE drop on a workcenter with sparse data?

> If `len(recent) < 3` or `len(prior) < 3`, skip — too noisy.

**Q4.** MPS approval pending > 7 days. Action?

> Recommendation to planner: "approve or reject these N pending
> periods."

**Q5.** Wire a new MES signal — where?

> Add `_check_<new_signal>` method, call from `_check_mes_signals`,
> include in `_check_all` chain (already happens via inheritance).
