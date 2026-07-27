---
course: 28
chapter: 28.2
title: Exec Dashboard Module — Tile Compute Pattern and Cron
duration: 7
audience: Developer working on tile compute logic
prereqs: Lesson 28.1
custom_modules: southbrook_exec_dashboard
---

# Exec Dashboard Module — Tile Compute Pattern and Cron

## Compute method return shape

Every compute method returns the same shape:

```python
{
    "title": "Quality Health",  # display label
    "value": "3 critical NCRs", # primary value
    "subtitle": "12 open total", # secondary
    "color": "amber",            # green/amber/red/grey
    "trend": [5, 4, 6, 3, 4],    # last N values for sparkline
    "drill_action": "southbrook_quality.action_southbrook_ncr",
    "drill_domain": [("state", "in", ["open", "quarantine"])],
}
```

## Example compute methods

### KPI tile

```python
class SouthbrookMiEngine(models.AbstractModel):
    _inherit = "southbrook.mi.engine"
    
    @api.model
    def get_quality_health_tile(self):
        ncrs = self.env["southbrook.ncr"].search([
            ("state", "in", ["open", "quarantine"]),
        ])
        critical = ncrs.filtered(lambda n: n.severity == "critical")
        color = "red" if critical else "amber" if ncrs else "green"
        return {
            "title": "Quality Health",
            "value": f"{len(critical)} critical NCRs",
            "subtitle": f"{len(ncrs)} open total",
            "color": color,
            "trend": self._quality_trend_last_7d(),
            "drill_action": "southbrook_quality.action_southbrook_ncr",
            "drill_domain": [("state", "in", ["open", "quarantine"])],
        }
```

### Trend tile

```python
@api.model
def get_wip_trend_tile(self):
    snapshots = self._wip_last_30_days()
    current = snapshots[-1] if snapshots else 0
    return {
        "title": "WIP Trend",
        "value": f"${current:,.0f}",
        "color": self._wip_color(current),
        "trend": snapshots,
        "drill_action": "southbrook_finance_pack.action_wip_report",
    }
```

### Hermes-flagged tile

```python
@api.model
def get_hermes_flagged_tile(self):
    recs = self.env["hermes.recommendation"].search([
        ("state", "=", "pending_review"),
        ("persona", "in", self._user_personas()),
    ])
    return {
        "title": "Awaiting Your Review",
        "value": f"{len(recs)} flagged",
        "color": "amber" if recs else "green",
        "list": [{"id": r.id, "subject": r.subject} for r in recs[:5]],
        "drill_action": "hermes.action_recommendations",
    }
```

## Cron-based refresh

```python
@api.model
def _cron_refresh_tiles(self):
    """Every 5 minutes: refresh tiles past their refresh_interval."""
    now = fields.Datetime.now()
    
    for tile in self.search([]):
        stale_after = (tile.last_computed_at or
                       fields.Datetime.from_string("2000-01-01")) + \
                      relativedelta(minutes=tile.refresh_interval_min)
        if now < stale_after:
            continue
        
        try:
            result = tile.compute()
            tile.write({
                "last_value_json": json.dumps(result),
                "last_computed_at": now,
            })
        except Exception as e:
            tile.message_post(body=_("Compute failed: %s") % str(e))
```

Cron runs every 5 minutes; tiles with longer refresh_interval
just skip.

## Live override

For tiles users want fresh:

```python
def force_refresh(self):
    self.ensure_one()
    self.last_computed_at = False  # invalidate cache
    return self.compute()
```

Triggered from the OWL component's "refresh" icon.

## Common mistakes + how to recover

- **"Return shape inconsistent"** — different tiles return different
  keys. The OWL template gracefully handles missing keys, but
  warnings emit. Standardise.
- **"Tile compute slow"** — heavy DB query. Optimise OR cache the
  intermediate via Postgres MATERIALIZED VIEW.
- **"`trend` field huge"** — limit to last 7 or 30 data points.

## Quiz

**Q1.** Return shape includes `color`. Acceptable values?

> green / amber / red / grey. Drives OWL component's CSS class.

**Q2.** Tile with `refresh_interval_min = 60`. Cron runs every
5 min. Re-computes how often?

> Hourly. Cron skips tiles still within their interval.

**Q3.** Compute method raises exception. Effect on tile_value?

> `last_value_json` stays old. Chatter logs error. UI shows
> stale data + a "stale" badge (depending on UI).

**Q4.** Drill_action = "module.action_name". Format?

> XML reference. Resolved client-side to load the act_window.

**Q5.** New compute method that returns inconsistent keys — what
happens?

> OWL template uses defaults; missing keys = empty cell. Add
> validation in the model to enforce shape.
