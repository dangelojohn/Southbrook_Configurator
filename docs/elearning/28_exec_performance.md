---
course: 28
chapter: 28.7
title: Exec Dashboard Module — Performance and Caching
duration: 6
audience: Developer optimising dashboard load times
prereqs: Lessons 28.1-28.6
custom_modules: southbrook_exec_dashboard
---

# Exec Dashboard Module — Performance and Caching

## The performance triangle

Three optimisation axes:

1. **Tile compute time** — how long each method takes
2. **Refresh interval** — how often computes run
3. **API response time** — what the user actually waits

## Tile compute time

Slow tiles dominate the cron's runtime. Profile via:

```python
import time

def compute(self):
    start = time.time()
    result = self._do_compute()
    elapsed = time.time() - start
    if elapsed > 2.0:
        _logger.warning(
            "Slow tile %s: %.2fs", self.tile_code, elapsed)
    return result
```

Aim for < 1 second per tile. If a compute is heavier:
- Cache intermediates in DB
- Use materialised views for aggregates
- Pre-compute via cron, not on demand

## Refresh interval tuning

```
Acceptable freshness  vs  Server load
5 min                     High (12 computes/hour)
15 min                    Moderate (4/hour)
60 min                    Low (1/hour)
```

For real-time operational signals: 5 min.
For trends / weekly views: 60 min.
For strategic / monthly: 24h.

## API response time

The exec dashboard API endpoint should respond < 200ms.
Approaches:

### 1. Pre-aggregate
Don't compute on request; serve `last_value_json` from DB.

```python
@api.model
def get_dashboard_data(self):
    tiles = self.search([...])
    return [{
        "id": t.id,
        **json.loads(t.last_value_json or "{}"),
    } for t in tiles]
```

Single query → fast.

### 2. Edge caching
If your dashboard is publicly cacheable (rare for exec
dashboard), use Caddy / Cloudflare cache.

### 3. Client-side caching
Browser cache for sparkline images. Don't cache the API itself.

## Materialised views for aggregates

Some computes can be backed by PostgreSQL materialised views:

```sql
CREATE MATERIALIZED VIEW mv_daily_revenue AS
SELECT DATE_TRUNC('day', date) AS day, SUM(amount_total) AS rev
FROM account_move
WHERE move_type = 'out_invoice'
  AND state = 'posted'
  AND date >= NOW() - INTERVAL '90 days'
GROUP BY 1;
```

Refresh nightly via cron:

```python
@api.model
def _cron_refresh_mvs(self):
    self.env.cr.execute("REFRESH MATERIALIZED VIEW mv_daily_revenue;")
```

Tile reads from MV instantly.

## Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
self.env["southbrook.mi.engine"].get_quality_health_tile()
profiler.disable()

stats = pstats.Stats(profiler).sort_stats("cumulative")
stats.print_stats(20)
```

Identifies hot spots.

## Memory usage

Each tile's `last_value_json` < 10 KB typically. With 50 tiles
and full sparklines, ~500 KB total per user. Fine.

Watch for:
- Large list payloads
- Embedded base64 images (don't do this)
- Trend arrays > 100 points

## Common mistakes + how to recover

- **"Dashboard loads slowly first time"** — likely cold cache.
  Pre-warm via a cron that triggers `get_dashboard_data` on
  startup.
- **"Tile shows briefly then disappears"** — OWL render error.
  Check browser console.
- **"Memory growth in worker"** — caching beyond worker
  lifetime; verify no global dicts.

## Quiz

**Q1.** Slow tile dominates the cron. Approach?

> Profile to find the hot spot. If a single query, optimise it.
> If many queries, consider materialised view.

**Q2.** Materialised view refreshes nightly. Latency impact?

> Tile shows yesterday's data until refresh runs. Acceptable for
> trend tiles; not for real-time operations.

**Q3.** Tile compute takes 5 seconds. What to do?

> Pre-compute via cron; tile reads cached value. User wait =
> ~10ms (DB read).

**Q4.** Dashboard load time = 3 seconds. Acceptable?

> Too slow. Aim for < 500ms. Profile API endpoint; likely
> heavy compute on request.

**Q5.** Sparkline with 1000 data points per tile. Effect?

> Heavy payload + slow OWL render. Limit to 30 points; aggregate
> server-side if needed.
