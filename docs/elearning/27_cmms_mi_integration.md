---
course: 27
chapter: 27.6
title: CMMS + WMS Module — MI Engine Integration
duration: 5
audience: Developer extending CMMS signals to MI engine
prereqs: Lessons 27.1-27.5
custom_modules: southbrook_cmms_wms, southbrook_manufacturing_intelligence
---

# CMMS + WMS Module — MI Engine Integration

## Signals surfaced

1. **Critical breakdown opened** → recommendation for Plant GM
2. **MTBF dropped > 30% week-over-week** → for maintenance lead
3. **Service contract expiring in N days** → for ops manager
4. **Oversize permit expiring** → for ops manager

## Hook

```python
class MiEngineCmmsExt(models.AbstractModel):
    _inherit = "southbrook.mi.engine"
    
    @api.model
    def _check_cmms_signals(self):
        self._check_critical_breakdowns()
        self._check_mtbf_trends()
        # Service contract + oversize handled by their own crons
    
    def _check_critical_breakdowns(self):
        critical = self.env["southbrook.cmms.breakdown_alert"].search([
            ("state", "=", "open"),
            ("severity", "=", "critical"),
        ])
        for alert in critical:
            self._emit_recommendation(
                subject=f"CRITICAL: {alert.equipment_id.name} down",
                body=alert.description or "",
                affected_records=alert,
                persona="mfg_manager",
            )
    
    def _check_mtbf_trends(self):
        # Compare last 7 days' avg MTBF to prior 7 days'
        for equip in self.env["maintenance.equipment"].search([]):
            recent_reports = self.env["southbrook.cmms.mtbf_mttr_report"].search([
                ("equipment_id", "=", equip.id),
                ("as_of_date", ">", fields.Date.today() - relativedelta(days=7)),
            ])
            prior_reports = self.env["southbrook.cmms.mtbf_mttr_report"].search([
                ("equipment_id", "=", equip.id),
                ("as_of_date", "<=", fields.Date.today() - relativedelta(days=7)),
                ("as_of_date", ">", fields.Date.today() - relativedelta(days=14)),
            ])
            if recent_reports and prior_reports:
                recent_mtbf = sum(r.mtbf_hours for r in recent_reports) / len(recent_reports)
                prior_mtbf = sum(r.mtbf_hours for r in prior_reports) / len(prior_reports)
                if prior_mtbf > 0 and (prior_mtbf - recent_mtbf) / prior_mtbf > 0.30:
                    self._emit_recommendation(
                        subject=f"{equip.name} MTBF dropping ({recent_mtbf:.0f}h vs {prior_mtbf:.0f}h)",
                        body="MTBF has degraded > 30% week-over-week. "
                             "Investigate root cause; may need preventive intervention.",
                        persona="maintenance_lead",
                    )
```

## Tile integration

CMMS contributes to the Equipment Health MI tile:

```python
def get_equipment_health_tile(self):
    open_critical = self.env["southbrook.cmms.breakdown_alert"].search_count([
        ("state", "in", ("open", "dispatched")),
        ("severity", "=", "critical"),
    ])
    avg_availability = self._avg_availability_pct()
    
    color = "red" if open_critical > 0 \
            else "amber" if avg_availability < 90 \
            else "green"
    
    return {
        "title": "Equipment Health",
        "value": f"{open_critical} critical, {avg_availability:.0f}% avail",
        "color": color,
    }
```

## Common mistakes + how to recover

- **"Critical breakdown rec fires every day"** — dedup not by
  alert id. Same alert should produce one rec, not daily refresh.
- **"MTBF trend rec triggers for new equipment"** — guard
  `if prior_reports and recent_reports` covers this.
- **"Service contract renewal rec fires too late"** — `cron_check_renewals`
  schedule wrong, OR `renewal_reminder_days` too low.

## Quiz

**Q1.** Critical breakdown opened today. When does rec emit?

> Next MI engine cron tick. Subject deduped against existing
> pending_review recs.

**Q2.** MTBF trend signal — minimum data required?

> ≥3 reports in each window (recent + prior). Avoid noise on
> single-data-point windows.

**Q3.** Equipment health tile colour green vs red?

> Green = no critical alerts AND avg availability ≥ 90%.
> Red = at least 1 critical OR availability < 70%.
> Amber = otherwise.

**Q4.** New signal: "spare parts inventory low for high-risk
equipment." Where?

> New `_check_*` method in `_check_cmms_signals`. Joins
> `maintenance.equipment.spare_part_ids` with stock levels.

**Q5.** Service contract renewal vs CMMS MI hook — different?

> Contract renewal has its own cron (`cron_check_renewals`).
> MI engine doesn't duplicate; both can co-exist surfacing same
> recommendation.
