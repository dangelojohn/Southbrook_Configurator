---
course: 18
chapter: 18.1
title: Quality Inspector — Your Menu and Your Role
duration: 12
audience: New quality inspector or quality manager onboarding to the Southbrook Quality module
prereqs: Basic Odoo navigation (login, menus, list/form views)
custom_modules: southbrook_quality
---

# Quality Inspector — Your Menu and Your Role

## Who this lesson is for

You're a quality inspector at Southbrook — or you're stepping into the
quality manager role. Either way this lesson hands you the map: what
menus you'll live in every day, what each submenu's job is, and where
the boundaries are between your work and the work of production, design,
and purchasing.

## Where this lives on the site

**Quality** (root menu, `menu_southbrook_quality_root`, declared in
`southbrook_quality.views.southbrook_quality_menus`).

Submenus, in display order:

| Submenu | XML id | What it's for |
|---|---|---|
| NCRs | `menu_southbrook_quality_ncr` | Open non-conformance records. Your main inbox. |
| SPC | `menu_southbrook_quality_spc` | Statistical Process Control sample entry + charts. |
| Cpk | `menu_southbrook_quality_cpk` | Process capability reports rolled up from SPC. |
| Dimensions | `menu_southbrook_quality_dimensions` | Master spec of every measured feature (USL/LSL/nominal). |
| Supplier Defects | `menu_southbrook_quality_supplier_defects` | Defects traced to incoming materials. |
| MI Tiles | `menu_southbrook_quality_mi_tiles` | Quality views of the MI dashboard. |

## What your screen shows

Each submenu lands you on a list view with consistent visual cues:

- **NCRs list** — decoration-warning rows = open NCRs > 7 days. Decoration-
  danger = severity `critical`. Decoration-info = state `quarantine`.
- **SPC list** — last 20 samples per dimension; chart preview on the form.
- **Cpk list** — each row is a computed report; columns include `cpk`,
  `cp`, `mean`, `stdev`, `period_days`.
- **Dimensions** — read-only for inspectors; the quality manager + ENG can
  edit. Shows `name`, `nominal`, `usl`, `lsl`, `unit_of_measure`,
  `applicable_workcenter_ids` (m2m).
- **Supplier Defects** — list grouped by `supplier_id` by default; can
  toggle to group by `product_id`.

## Your daily flow

A typical inspector's day, in 6 phases:

### 1. Morning scan (15 min)
- Open *Quality → NCRs*, filter `state = open` + `severity in (major, critical)`.
- Read each one's chatter to know what's evolved overnight.
- Open *Quality → MI Tiles* — the *Quality Health* tile shows
  yesterday's NCR count + open age + critical count. If the trend is
  bad, that becomes the first thing to brief the Plant GM about.

### 2. Sampling rounds (every 2 hours)
- Walk the floor; pull samples per the SPC plan
  (`quality.dimension.sample_frequency`).
- Enter samples into *Quality → SPC* immediately (don't accumulate on
  paper — the chart's trend signal degrades).

### 3. NCR response (as alerts fire)
- Inline NCRs created from the floor (see Course 1 lesson 1.6 and
  Course 17 lesson 17.23 / 17.28) drop into your queue with a
  notification.
- Triage: `severity = critical` blocks the line; you get pulled to it.
  `major` blocks the cabinet but not the line; `minor` is informational.
- Decide: rework / scrap / accept (see lesson 18.2).

### 4. Supplier defects (as incoming receipts hit you)
- When receiving creates damaged materials, the team logs a
  `southbrook.quality.supplier_defect` linked to the PO. You verify the
  link is accurate + severity is honest.
- Score recompute is nightly (see lesson 18.5).

### 5. Cpk / capability work (weekly)
- Each Friday, run Cpk on the top 5 dimensions by sample volume (lesson
  18.4). Trend the numbers; pre-empt the dimensions drifting toward
  out-of-spec.

### 6. End-of-day handoff
- Post a brief chatter on any NCR still open at shift end.
- Open *Quality → MI Tiles* once more — confirm today's count vs your
  morning baseline. Yesterday + today's deltas are how the Plant GM
  reads quality at the morning briefing.

## Common mistakes + how to recover

- **"I keep getting paged for NCRs I already triaged."** Activity
  assignment was left blank or routed to the queue-default. Open the
  NCR → assign the activity to a specific user (yourself or the rework
  team) to take it out of the *general* queue.
- **"I marked an NCR `accept` but the cabinet still has a quarantine
  badge."** The `mrp.workorder` block doesn't auto-clear on the
  cabinet's downstream WOs; open the NCR's *Affected MOs* tab → *Unblock
  Downstream*.
- **"My SPC chart hasn't updated after I entered a sample."** A 60-second
  cache delay on the chart render. Refresh; if still stale, the
  dimension master may have changed during the period — see lesson 18.3.
- **"Supplier scorecards look static."** Recompute is nightly, not
  immediate. Today's defects don't show until tomorrow's MI run.

## What the system is doing behind the scenes

- Every NCR write fires a `mail.activity` to the assigned user via
  `mail.thread`.
- SPC entry triggers a `southbrook.quality.spc_sample.create` which the
  MI engine subscribes to — if the sample breaches control limits, MI
  posts a recommendation to the Plant GM's Hermes queue.
- Cpk reports cache results on the report record for the period, so
  re-opening doesn't recompute. To force fresh math, click *Compute*.
- The Supplier Defect → scorecard rollup is a cron in
  `southbrook_quality.mi_engine_ext` that runs at 03:30 nightly (see
  Course 7 lesson 7.1 for the orchestration cron list).

## Quiz (5 questions, applied)

**Q1.** You arrive Monday morning and the NCR queue shows 14 open
records, 3 critical. What's the first action?

> Open *Quality → MI Tiles* and check the Quality Health tile to see the
> weekend's trend, THEN dive into the 3 critical NCRs by severity +
> reported_at desc. Sorting by date first risks missing a critical that
> came in earlier.

**Q2.** A floor operator pings you: their kanban shows a cabinet with a
red border and they can't tap *Done*. Which menu do you check?

> *Quality → NCRs* with filter `production_id = <their MO>`. The red
> border = quarantine state from an open inline NCR. Triage that NCR
> before the cabinet can move.

**Q3.** Quality manager says supplier Marathon's defect rate "looks
fine" today. The supplier scorecard backs it up. You logged 3 defects
yesterday. What's the most likely explanation?

> Scorecard recompute is nightly via the MI engine cron. Yesterday's
> defects don't show until after the 03:30 run today — visible in
> *Quality → MI Tiles* once the cron lands.

**Q4.** SPC chart for *panel thickness on SB-CNC-BORE* shows a point
breaching UCL. You enter a new sample 30 minutes later that's back in
range. Do you still file an NCR?

> Yes if any cabinets passed during the breach window. The breach point
> represents real out-of-control output; even if the next sample
> recovers, what came off during the breach is suspect. File an NCR on
> the affected MO range.

**Q5.** You see a Cpk report card showing `cpk = 0.85`. The process has
been running clean (no scrap) for a month. What's going on?

> Cpk < 1.0 means the process spec is wider than what the math says
> you're producing — but you're not catching scrap because the
> engineering spec (USL/LSL) is generous. Either tighten the spec to
> match reality, or accept the math says "could fail" but observed
> behavior says "doesn't."

## What this lesson does NOT cover

- The specifics of opening an NCR — see lesson 18.2.
- The specifics of SPC sample frequency + when to halt — see lesson 18.3.
- The math behind Cpk + what to do with it — see lesson 18.4.
- Supplier scoring math + monthly review meeting — see lesson 18.5.
- Native Odoo Quality module (we're not running it; the Southbrook quality
  layer is the source of truth).
