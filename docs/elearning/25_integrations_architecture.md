---
course: 25
chapter: 25.1
title: Integrations Module — Architecture
duration: 7
audience: Developer learning the southbrook_integrations layout
prereqs: Python + Odoo + basic API integration concepts
custom_modules: southbrook_integrations
---

# Integrations Module — Architecture

## The module at a glance

- Path: `addons/southbrook_integrations/`
- Version: 19.0.1.0.0
- Depends on: `base`, `mail`, `mrp`, `stock`, `purchase`,
  `account`, `southbrook_manufacturing_intelligence`

## Source layout

```
addons/southbrook_integrations/
├── models/
│   ├── homag_session.py          — Homag iX simulator session
│   ├── homag_msg.py              — messages exchanged
│   ├── asn_inbound.py            — 3PL inbound ASN
│   ├── asn_outbound.py           — outbound ASN
│   ├── mcp_tool.py               — MCP server tool registry
│   ├── mcp_call_log.py           — MCP call audit
│   ├── label_printer.py          — physical printer config
│   └── label_log.py              — print history
├── controllers/
│   ├── mcp_api.py                — MCP HTTP endpoints
│   ├── asn_api.py                — ASN webhook receivers
│   └── label_api.py              — label print API
├── views/
└── data/
```

## The 4 integration domains

### 1. Homag iX (manufacturing equipment)

Simulator + planned-live integration with Homag's iX platform for
edge bander + CNC programs. Sends cabinet specs; receives nest /
program files.

Models: `homag_session`, `homag_msg`.

### 2. 3PL ASN (logistics)

Advance Shipment Notice — inbound (3PL → Southbrook) for
inventory receipts, outbound (Southbrook → 3PL) for shipments.

Models: `asn_inbound`, `asn_outbound`.

### 3. MCP server (AI tooling)

Model Context Protocol tool registry — read-only data access for
self-hosted Qwen LLM (future). Distinct from Hermes' tool
registry (different security model, different consumers).

Models: `mcp_tool`, `mcp_call_log`.

### 4. Label printers (physical output)

Zebra ZPL + DataMax/Honeywell support for shipping labels +
shop-floor traveller tags.

Models: `label_printer`, `label_log`.

## Why one module instead of four

Each integration is small enough that a separate addon would be
ceremony overhead. They share:
- Common error logging pattern
- MI engine integration for status surfacing
- A consistent "session / message / log" record pattern

The cost of separation > value at v1. Split later if any of them
grows substantially.

## Install

```bash
./scripts/deploy_to_qnap.sh southbrook_integrations
```

What -i does:
1. Creates 8 tables
2. Adds the 7 menus under Integrations
3. Registers 2 crons (Homag heartbeat, label log cleanup)

## Cron landscape

| Cron | Schedule | Purpose |
|---|---|---|
| `cron_homag_heartbeat` | every 5 min | Pings the Homag iX server to detect outages |
| `cron_label_log_cleanup` | 02:00 daily | Archives label logs older than 90 days |

## Common mistakes + how to recover

- **"MCP endpoint 404"** — module installed but new routes need
  SIGHUP. `docker exec southbrook-odoo kill -HUP 1`.
- **"Homag session log empty"** — Homag simulator not configured.
  Set `southbrook_integrations.homag.endpoint` system parameter.
- **"Label printer offline"** — physical printer issue;
  monitoring tile shows status from heartbeat.

## Quiz

**Q1.** Why combine Homag + ASN + MCP + Label printers?

> Each is small at v1; sharing logging + MI patterns. Split later
> if growth warrants.

**Q2.** What native module dependencies?

> `mrp` (for production-related ASN), `stock` (for warehouse),
> `purchase` (for ASN inbound), `account` (for ASN journal).

**Q3.** Homag heartbeat cron — what does it do?

> Pings the Homag iX server every 5 minutes; logs status to
> `homag_session` records. Alerts if 3 consecutive pings fail.

**Q4.** MCP vs Hermes tool registry — what's different?

> Hermes is persona-bound (JWT-claim-driven), serves trade
> partners on edge. MCP is model-bound (one row per `model_id`),
> read-only, serves self-hosted Qwen LLM with X-Api-Key auth.

**Q5.** Label log cleanup cron — preserves what?

> Last 90 days. Older entries archived to `ir.attachment` CSV
> bundle if needed for compliance.
