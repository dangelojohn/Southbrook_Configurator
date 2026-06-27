---
course: 25
chapter: 25.7
title: Integrations Module — Monitoring and Observability
duration: 6
audience: Sysadmin or developer monitoring integration health
prereqs: Lessons 25.1-25.6
custom_modules: southbrook_integrations
---

# Integrations Module — Monitoring and Observability

## What to monitor

Per integration:
- Heartbeat last_seen
- Recent error count
- Recent latency
- Recent volume

## MI tile

The Integrations MI Tile aggregates all integrations:

```python
class IntegrationsMiTile(models.AbstractModel):
    _inherit = "southbrook.mi.tile"
    
    @api.model
    def get_integrations_tile(self):
        homag_status = self._get_homag_status()
        asn_status = self._get_asn_status()
        mcp_status = self._get_mcp_status()
        printers_status = self._get_printers_status()
        
        overall = "red" if any(s == "red" for s in [
            homag_status, asn_status, mcp_status, printers_status]) \
            else "amber" if any(s == "amber" for s in [...]) \
            else "green"
        
        return {
            "title": "Integrations Health",
            "value": overall,
            "subtitles": {
                "Homag": homag_status,
                "ASN (3PL)": asn_status,
                "MCP": mcp_status,
                "Printers": printers_status,
            },
            "color": overall,
        }
```

## Log models for audit

Each integration has its own log:
- `homag_msg` — Homag I/O
- `asn_inbound` / `asn_outbound` — ASN history
- `mcp_call_log` — MCP API calls
- `label_log` — print history

Together = full integration audit trail.

## Common queries

### "Why was Vendor X down last week?"

```sql
SELECT DATE_TRUNC('hour', taken_at) AS hour,
       status,
       COUNT(*) AS count
FROM southbrook_integrations_vendorx_log
WHERE taken_at > NOW() - INTERVAL '7 days'
GROUP BY hour, status
ORDER BY hour;
```

Shows hourly status breakdown.

### "Which 3PL has highest error rate?"

```sql
SELECT partner_id,
       COUNT(*) FILTER (WHERE state = 'error') * 100.0 / COUNT(*) AS error_pct
FROM southbrook_integrations_asn_inbound
WHERE create_date > NOW() - INTERVAL '30 days'
GROUP BY partner_id
ORDER BY error_pct DESC;
```

## Alerts

The MI engine emits recommendations:
- Heartbeat failure for > 15 minutes
- > 10% error rate in last hour
- > 50% latency spike vs baseline

## Common mistakes + how to recover

- **"Tile shows green but I'm seeing problems"** — tile cache
  may be stale. Refresh.
- **"Heartbeat ran but status not updated"** — cron error;
  check `ir.cron.lastcall`.
- **"Logs full of errors but no recommendation"** — MI engine
  threshold not exceeded. Tune.

## Quiz

**Q1.** Integrations MI tile colour green vs red — what triggers?

> Green = all four integrations green. Red = any integration red.
> Amber = some amber, none red.

**Q2.** Audit trail — which models?

> homag_msg, asn_inbound, asn_outbound, mcp_call_log, label_log.

**Q3.** Vendor X down for 5 minutes. Recommendation fires?

> Depends on threshold (`> 15 min` typical). 5 minutes alone =
> nothing. Sustained 15+ = fire.

**Q4.** SQL query: which integrations had > 10 errors last 24h?

> Query log tables filtered by status=error + create_date > 24h
> grouped by integration type.

**Q5.** Tile not updating — first investigation step?

> Check the cron that powers the tile compute. View
> `ir.cron.lastcall` + status.
