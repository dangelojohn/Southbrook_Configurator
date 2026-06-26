---
course: 21
chapter: 21.2
title: Executive — Drilling Into a Tile
duration: 8
audience: Owner or Plant GM going beyond the 5-minute scan
prereqs: Lesson 21.1
custom_modules: southbrook_exec_dashboard
---

# Executive — Drilling Into a Tile

## Who this lesson is for

You did the 5-minute scan; one tile caught your attention. This
lesson is the next 15 minutes — how to go from "amber" to "I
understand what's happening + I know what to do."

## Where this lives on the site

Click any tile on the Exec Dashboard to drill. Each tile has a
drill-through target — usually the underlying list view filtered to
the relevant data.

## The drill-through pattern, by tile category

### Sales / Cash tiles
- **Yesterday revenue** → invoice list filtered to yesterday
- **AR aged 60+** → invoice list filtered to overdue
- Drill question: which customers? which industries? any single
  outlier?

### Production tiles
- **Today plan** → work order list for today
- **WIP** → WIP report grouped by team
- **OEE** → workcenter list with OEE per
- Drill question: where's the bottleneck? whose workcenter? what
  product family is heaviest?

### Quality / Maintenance tiles
- **Open NCRs** → NCR list filtered by state + severity
- **Breakdown alerts** → alert list filtered by state
- Drill question: what's the pattern? supplier-driven? operator
  shift? specific equipment?

### Hermes tiles
- **Flagged items** → recommendation list, pending review
- Drill question: each is a separate decision — read + decide

## A worked example: AR aged 60+

You see this in amber: **$45k / 6 customers**.

### Drill click

Lands you on the aged invoice list, filtered to AR > 60 days.

### Step 1: Sort by amount descending
- Top of the list is your biggest exposure
- Read the customer name + invoice age

### Step 2: Read the chatter on the top 3
- The chatter has the history — who's been called, who promised
  when, who's disputing
- 30 seconds each

### Step 3: Categorise mentally
- **Already promised** — your team is on it
- **Disputed** — need ownership decision: chase legal or write off
- **Forgotten** — needs a chase today

### Step 4: Act
- Walk to AR clerk: "what's happening with Customer X?"
- Call the customer yourself if the relationship warrants it
- Decide on write-off thresholds with the controller

### Step 5: Document
- Add a chatter post to the affected invoices with your decision
- "Spoke to John Doe; he'll wire by Friday" — captures intent

## A worked example: Open NCRs (critical = 2)

You see: 2 critical NCRs.

### Drill click

NCR list filtered to `state = open AND severity = critical`.

### What to look for in the form

- `production_id` — which MO?
- `defect_type` + `severity` — what kind of defect?
- `reported_at` — how long open?
- `chatter` — what's happening?

### The question to ask yourself

- Is this customer-facing?
- Is the cabinet en route to a delivery?
- Does Quality have a plan?

### When to intervene

- If the cabinet is critical-path AND Quality is overwhelmed: ask
  who you can spare from another team to help triage
- If the defect points at a systemic issue (multiple cabinets,
  pattern by workcenter): escalate to Quality manager for an ECO
  conversation (lesson 17.10)
- If neither: trust Quality; check back tomorrow

## A worked example: OEE on SB-CNC-BORE is amber

You see: SB-CNC-BORE OEE 71% (target 85%).

### Drill click

Workcenter form for SB-CNC-BORE → OEE breakdown:
- Availability %
- Performance %
- Quality %

### The OEE math

OEE = Availability × Performance × Quality

- **Availability < target** — workcenter was down (breakdown? PM?
  setup?)
- **Performance < target** — running slow (operator training? tool
  wear? wrong program?)
- **Quality < target** — too much scrap or rework (lesson 21.3)

Each factor points to a different intervention.

## Common mistakes + how to recover

- **"I drill in but don't know what I'm looking at."** The list
  view shows the underlying records. If the model isn't familiar,
  call the relevant department lead for a 5-minute walk-through.
  Each module has a deep-dive course (Courses 8-15 + 18-21).

- **"The list view shows 200 records; where do I start?"** Sort
  + filter. Top 10 by amount + age combination is usually right.
  If that's not enough, ask "what's the question?" — then refine
  the filter.

- **"I drill, see the data, but can't tell if it's bad."**
  Compare to last week, last month. Use the form's chatter for
  history; use *Reporting → [something]* for trends.

- **"I find a problem and want to fix it myself."** Generally:
  no. Surface it to the responsible lead. Your job is direction +
  decisions, not fixing fields. Exception: critical-path operations
  where speed matters and you have the context.

- **"My drill-through gives different numbers than the tile."**
  The tile cached at 5-min; the list view is live. Refresh the
  tile (cog menu) if the gap matters.

## What the system is doing behind the scenes

- Tile click navigates to the configured `action_id` with filters
  pre-applied
- The list view runs the same domain that the tile compute did
- No magic — just a saved filter + a tile-to-action mapping

## Quiz (5 questions, applied)

**Q1.** AR aged 60+ tile shows $45k. Drilling, 4 customers have
$8k each, one customer has $13k. Where do you focus?

> The $13k customer. Largest single exposure. Read their chatter.
> Decide chase / write-off / dispute. The 4 × $8k can be batched to
> the AR clerk.

**Q2.** OEE on SB-EDGE is 65%. Drill shows availability 75%,
performance 92%, quality 94%. What's the root cause?

> Availability — the biggest deviation from target. Workcenter was
> down too much. Causes: breakdown (check CMMS), PM (planned), or
> setup time (operator issue). Walk to maintenance + edge banding
> supervisor.

**Q3.** Breakdown alert tile shows 1 open + 3 dispatched. The 1
open is critical. Action?

> Drill the open alert. Read it. If maintenance lead isn't on it
> already, call them now. If they ARE on it, your tile may be
> stale — refresh.

**Q4.** Today plan tile shows "94 work orders." Drilling, 30 are
scheduled with no assigned workcenter. What's wrong?

> Likely an upstream MRP run that didn't fully schedule. Walk to
> the production planner. Could be a workcenter capacity overflow
> (lesson 17.17 / 17.16) or a config issue.

**Q5.** Hermes-flagged tile has 4 items. Reading them: 2 are
"approve this rec for X" + 2 are "ack this status alert." Time
budget?

> Approvals — 2 minutes each (read context + click). Acks — 30
> seconds each (read + dismiss). Total < 5 min. The day's small
> tax.

## What this lesson does NOT cover

- OEE deeper math + bottleneck-specific reading — lesson 21.3.
- Approving Hermes recs in depth — lesson 21.4.
- Specific module forms (each module course covers its specifics).
