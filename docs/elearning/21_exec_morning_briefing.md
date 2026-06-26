---
course: 21
chapter: 21.1
title: Executive — The 5-Minute Morning Briefing
duration: 6
audience: Owner, Plant GM, or executive doing the daily morning scan
prereqs: Basic platform familiarity
custom_modules: southbrook_exec_dashboard
---

# Executive — The 5-Minute Morning Briefing

## Who this lesson is for

You're the owner or Plant GM. You have 5 minutes in the morning before
the rest of the day eats you. This lesson is the discipline: what to
look at, what to skim, what to deep-dive, and what to ignore.

## Where this lives on the site

**Exec Dashboard** (root menu, `menu_exec_dashboard_root`).

Lands you on the mobile-first morning briefing OWL view — a single
page of tiles designed to be scannable on a phone over coffee.

## What your screen shows

### Tile layout (typical)

| Row | Tiles | Purpose |
|---|---|---|
| Top | Yesterday's revenue, today's plan, week-to-date | Cash flow scan |
| Middle | Open NCRs, breakdown alerts, OEE | Operational health |
| Lower | WIP, AR aged 60+, top-3 risk projects | Risk surface |
| Bottom | Hermes-flagged items needing attention | Inbox of executive actions |

### Tile colour coding

- **Green** — within target; no action needed
- **Amber** — below target but expected variation; watch
- **Red** — significant miss; needs attention this week
- **Grey** — no data (configuration issue OR nothing happened)

## The 5-minute scan, by minute

### Minute 1: Cash flow
- Yesterday's revenue tile — within ±10% of 30-day average?
- Today's planned production tile — does the plan look real (no
  empty workcenters)?
- Week-to-date tile — pacing toward weekly target?

### Minute 2: Operational health
- Open NCRs — any critical? (Critical = red bordered)
- Breakdown alerts — any open? Any dispatched but not closed
  past 24h?
- OEE — any workcenter below its `oee_target`? Compare last 3 days
  trend

### Minute 3: Risk surface
- WIP value — within band of last week's average?
- AR aged 60+ — total dollar value + count of customers?
- Top-3 risk projects — names + the one-line reason they're risk?

### Minute 4: Executive actions
- Hermes-flagged items — read each one
- These are typically: approval requests, exception escalations,
  recommendations needing acknowledgment
- 30 seconds each; decide accept / defer / reject

### Minute 5: Quick decisions
- Walk away with 1-3 things to do today
- Walk away with 1-3 things to delegate
- Walk away with 0-2 things to escalate (banker, supplier, customer)

## What ALL TILES are reading

Each tile has a `tile_type` that drives the query. The major ones:

| Tile | Source model | Key compute |
|---|---|---|
| Yesterday revenue | `account.move.line` | Sum of invoiced sales `invoice_date = yesterday` |
| Today plan | `mrp.production` | Count of work orders scheduled today |
| Open NCRs | `southbrook.ncr` | `state IN (open, quarantine)` |
| Breakdown alerts | `southbrook.cmms.breakdown_alert` | `state IN (open, dispatched)` |
| OEE today | `mrp.workcenter` | Avg OEE for the day |
| WIP | `mrp.production` (WIP report) | Sum of `cost_so_far` |
| AR aged 60+ | `account.move` | Sum of unpaid + age > 60 |
| Hermes flagged | `hermes.recommendation` | State `pending_review` |

Tiles refresh every 5 minutes by default (configurable per tile).

## Reading the trend

Each tile shows current value + a sparkline of recent history. Worth
seeing:

- **Trend up + amber** — improving; OK
- **Trend down + green** — deteriorating from a comfortable starting
  point; watch
- **Flat + amber** — sustained miss; intervene
- **Spike + red** — something acute; act today

## When a tile is grey

Greys often mean configuration broke, not nothing happened. Walk:

1. Open the tile (most tiles drill-through to the source data)
2. If the source has data but the tile is grey, the compute may be
   stale (`southbrook_exec_dashboard.exec_tile.last_computed_at`)
3. Trigger a refresh via the cog menu
4. If still grey, escalate to sysadmin

## Common mistakes + how to recover

- **"I open the dashboard but it feels overwhelming."** That's the
  point on the first read. The discipline is to scan it in 5
  minutes — speed comes with practice. If you spend 30 min in the
  briefing, you're using it as a deep-dive tool; that's a
  different visit.

- **"I see red tiles every day; I tune them out."** The platform
  is over-alerting. Coordinate with Plant GM to tighten the
  `tile.threshold_*` configuration so red means actually red.

- **"Tiles look fine but my team says things are on fire."** The
  briefing aggregates; the team is dealing with specifics. Walk
  the floor at 10am for a reality check.

- **"I never see the Hermes-flagged items because they don't
  exist."** Hermes only flags when its loops surface something.
  No flags = either nothing to flag, or Hermes loops aren't
  running. Check sysadmin status if zero flags persist for days.

- **"Wrong tile values."** Source data may be wrong upstream;
  drill the tile to the source list view. Often quality issues
  (NCRs in wrong state) or accounting issues (invoices in draft).

## What the system is doing behind the scenes

- **OWL view** renders tiles client-side from a single JSON
  payload returned by the controller
- **Per-tile compute** runs cron at 5-min interval (configurable)
- **Hermes integration** subscribes to recommendation events; the
  Hermes-flagged tile pulls live
- **Mobile-first** layout — tiles re-stack vertically on
  narrow viewports

## Quiz (5 questions, applied)

**Q1.** Yesterday's revenue tile is green and showing $52k. Your gut
says it should be $80k. What's the first explanation?

> Filtering: maybe one large SO was billed across two days and
> shows on the other. Drill the tile — it lists the invoices
> contributing. If the invoices look complete, the gut may have
> been recalibrated by a recent slow week; if invoices are
> missing, accounting may have unposted drafts.

**Q2.** Breakdown alerts shows 3 dispatched, none open. Should you
worry?

> Not from this scan alone. Drill the tile; check the dispatched
> alerts' age. If any are dispatched > 24h, that's a flag —
> maintenance is slow OR a complex job is genuinely ongoing.
> Conversation with maintenance lead, not a panic.

**Q3.** WIP tile is grey. Source list view shows 80 active MOs.
What's happening?

> Tile compute is stale. Cog menu → *Refresh*. If still grey, the
> compute cron is broken — escalate to sysadmin.

**Q4.** Hermes-flagged shows 0 every day for a week. Possible?

> Yes — if the operational picture is genuinely healthy AND
> Hermes' confidence thresholds are conservative. But sustained
> 0 is also a sign that loops aren't running. Check the Hermes
> Console (Course 7 lesson 7.3) for loop health.

**Q5.** You have a banker meeting at 10am. The briefing shows AR
aged 60+ in amber. Your move?

> Drill the tile, identify the top-3 aged customers, decide which
> are at risk + which are routine. Bring numbers to the banker, not
> just the amber colour.

## What this lesson does NOT cover

- Drilling into specific tiles for deeper analysis — lesson 21.2.
- Reading OEE + bottleneck specifically — lesson 21.3.
- Approving Hermes recommendations — lesson 21.4.
- Per-tile configuration — admin task, separate from this lesson.
