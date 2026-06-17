---
course: 2 — Production Planning
chapter: 2.4
title: Premium Orchestration — The Six Nightly Crons
duration: 45 minutes
audience: Production Planner + Sysadmin (the two people who read cron output)
prereqs: Lessons 2.1-2.3. Comfort opening Odoo developer tools (Settings -> Technical -> Scheduled Actions).
custom_modules: southbrook_premium_orchestration
---

# Premium Orchestration — The Six Nightly Crons

## Who this lesson is for

You're the planner who walks in at 7am and sees a Kitchen Jobs card
flipped from green to red overnight — that was a cron. OR you're the
sysadmin who got paged at 03:14 because the data-quality dry-run
raised a warning in the logs — that was a cron too. Six scheduled
actions run automatically; you both need to know what each one does,
when it fires, what state it reads, what it writes, and what to do
when it fails. Without this lesson the platform feels like magic.
With it, you can answer "why is this card blocked?" in 30 seconds.

This is a longer lesson than the others because each cron is its own
sub-section. Skim the schedule table, then read the section for any
cron whose output landed in your queue.

## Where this lives on the site

For the planner (read-only effects):

> **Kitchen Ops -> Kitchen Jobs** — readiness flips by the readiness cron
> **Kitchen Ops -> MI Engine Status** — last-run telemetry from the MI refire cron
> **Kitchen Ops -> Production Release Queue** — release-state flips from the MI gate refire

For the sysadmin (the actual cron records):

> **Settings -> Technical -> Automation -> Scheduled Actions**

Filter by name containing `Southbrook:` to see all six. Each record
shows next fire time, last fire time, status, and the model + method
it calls. From there you can run **Run Manually** to fire a cron
out-of-cycle for debugging.

For each cron's last-run log:

> **Settings -> Technical -> Logging**

Filter by name containing the cron's model name (e.g.
`southbrook.mi.engine.state`, `southbrook.order.analytics`). Cron
runs emit one INFO line on a successful tick and one WARNING line per
in-tick exception that was caught.

## The schedule at a glance

| # | Name | Fires | Owner |
|---|---|---|---|
| 1 | Southbrook: Recompute Project Readiness | every 30 min | B1 |
| 2 | Southbrook: Refire MI Stage-Gate Checks | every hour | B3 |
| 3 | Southbrook: Backfill Order Analytics | every 6 hours | B2 |
| 4 | Southbrook: Weekly Planning Baseline | Sundays ~02:00 | B2 |
| 5 | Southbrook: Quality Dry-Run Nightly | nightly ~03:00 | B10 |
| 6 | Southbrook: Propose ECOs for High-Frequency Cut-Spec Overrides | nightly ~04:00 | B8 |

The first five are seeded in `data/ir_cron.xml`. The sixth is in
`data/eco_proposal_cron.xml`. All six are owned by `base.user_root`
(the system user) and stamped `noupdate="0"` so a `-u
southbrook_premium_orchestration` re-seeds anything an admin
accidentally archived.

Stagger note: the install code on each cron offsets `nextcall` by
+2/+5/+10/+0 minutes so the first run after install doesn't pile up
in the same minute. After that, each runs on its own cadence.

---

## Cron 1 — `cron_recompute_readiness_all`

**Name in UI:** Southbrook: Recompute Project Readiness
**Fires:** every 30 minutes (interval_number=30, interval_type=minutes)
**Model:** `project.task`
**Method:** `model._cron_recompute_readiness_all()`
**xml_id:** `southbrook_premium_orchestration.cron_recompute_readiness_all`

**What it does.** Sweeps every `project.task` that's linked to a
`sale.order` (via `x_southbrook_sale_order_id`) and is not in a closed
state. For each task, snapshots the current `readiness_decision` and
`southbrook_production_release_state`, calls the readiness recompute
method (`action_recompute_readiness_lines` from
`southbrook_project_mrp`), stamps `readiness_last_recomputed_at`, and
if the decision flipped between runs, posts a chatter note on the
task — that's the "Decision: ready -> blocked" line you see on the
chatter the next morning.

**What it reads.** All five readiness sub-signals (CAD, cutlist, BoM,
crew, equipment) plus the upstream artefacts each one is computed
from. Anything that contributes to the readiness lines.

**What it writes.** `readiness_decision`, `readiness_score`,
`readiness_last_recomputed_at` on the task. A chatter note when the
decision flips. Nothing else.

**Who cares.** The planner — every card on Kitchen Jobs is grouped by
`readiness_decision`, so this cron is what reshuffles your kanban
columns. Also the MI gate refire cron downstream, which uses the
readiness decision as one of its inputs.

**Reading its last run.** Open **Settings -> Technical -> Scheduled
Actions** -> find this record. The `Next Execution Date` field tells
you when it last fired (next call - 30 min). For per-task detail, open
a specific task and look at `readiness_last_recomputed_at` — that's
the exact timestamp.

**What to do if it errored.** The cron is per-task error-isolated — a
single failing task doesn't poison the whole sweep. If you suspect it
hung, check the cron's `nextcall` date — if it's stuck on a past time,
the previous tick never finished. Run it manually from Scheduled
Actions to test; if it errors immediately, the log will name the
failing task. Most common failure: the readiness recompute method
isn't on the task because `southbrook_project_mrp` was uninstalled or
its model name changed. The cron probes three method-name candidates
(`action_recompute_readiness_lines`, `action_recompute_readiness`,
`_recompute_readiness`) for migration tolerance, so a clean rename is
caught automatically.

---

## Cron 2 — `cron_mi_engine_refire_gates`

**Name in UI:** Southbrook: Refire MI Stage-Gate Checks
**Fires:** every 1 hour (interval_number=1, interval_type=hours)
**Model:** `southbrook.mi.engine.state`
**Method:** `model._cron_refire_gates()`
**xml_id:** `southbrook_premium_orchestration.cron_mi_engine_refire_gates`

**What it does.** Walks every in-flight `mrp.production` (state in
`confirmed` or `progress`) cross every active gate check
(`southbrook.mi.check` where `is_gate = True`), evaluates each check
against each MO, and counts the blockers/warnings. Writes a singleton
`southbrook.mi.engine.state` record with last_run telemetry: when it
ran, how many evaluations, how many blockers, how many warnings, how
many milliseconds it took.

**What it reads.** Every `southbrook.mi.check` with `is_gate=True`,
and the MO state, BoM, cutlist, hardware package state, and any
custom fields the check's evaluator method examines.

**What it writes.** The singleton state record's `last_run_at`,
`last_run_check_count`, `last_run_blockers`, `last_run_warnings`,
`last_run_duration_ms`. Indirectly, the per-MO gate flips that get
written by the check's own evaluator when it fires — these can flip
the release state from `ready` back to `blocked` and that surfaces
on the Production Release Queue.

**Who cares.** The planner — a release that was green at 09:00 can
be `blocked` again by 10:00 because of this cron. Also the production
manager (Course 3 audience), because gate flips are the recommendation
engine's main signal.

**Reading its last run.** Open **Kitchen Ops -> MI Engine Status**.
The form view shows the singleton record's last-run fields directly.
A green status banner with `last_run_blockers = 0` means clean.
There's also a manual **Run Now** button on the form (`action_run_now`)
that fires the cron synchronously and returns a popup notification.

**What to do if it errored.** The cron has per-check try/except around
each evaluator — one misbehaving check can't stall the whole run. The
WARNING log line names the failing check id + MO id; look up the
check, fix it, run the cron manually. If the cron is silently doing
nothing (e.g. `last_run_check_count = 0`), the most likely cause is
that no `southbrook.mi.check` records have `is_gate = True`. Probe
with `env['southbrook.mi.check'].search_count([('is_gate', '=', True)])`
in a shell.

---

## Cron 3 — `cron_backfill_order_analytics`

**Name in UI:** Southbrook: Backfill Order Analytics
**Fires:** every 6 hours (interval_number=6, interval_type=hours)
**Model:** `southbrook.order.analytics`
**Method:** `model._cron_backfill_unscored()`
**xml_id:** `southbrook_premium_orchestration.cron_backfill_order_analytics`

**What it does.** Finds confirmed sale.orders (`state = sale`) that
don't yet have a `southbrook.order.analytics` row, and calls the
analytics model's `capture()` method on each one. Idempotent —
re-running doesn't duplicate. Closes the historical-coverage gap that
existed before this cron (9 analytics rows on 92 confirmed orders).

**What it reads.** `sale.order` records via a raw `LEFT JOIN ... WHERE
soa.id IS NULL` SQL probe, then loads each missing one into the
analytics capture method which reads channel pricelist, line totals,
configurator session, customer specs.

**What it writes.** One `southbrook.order.analytics` row per
previously-uncaptured order, with the rollup fields the analytics
model defines (price, channel, line counts, etc).

**Who cares.** Sales-side analytics dashboards (Course 5 / 6
material). For the planner, only indirectly — accurate analytics
rows underpin the customer-specific lead-time estimates the
configurator quotes. Sysadmin cares because the cron is the safety
net for any order that was confirmed before the always-on
`action_confirm` override hook landed.

**Reading its last run.** Most direct: search the log filter by
"southbrook.order.analytics". The INFO line reads either
"no unscored orders, all confirmed orders already captured" (good)
or "%d unscored confirmed orders found, capturing..." followed by
"captured X / Y" (also good — that's normal backfill activity after
a bulk order import).

**What to do if it errored.** Per-order try/except — a single bad
order is logged as WARNING and the sweep continues. If the cron is
producing many WARNINGs, open one of the named order IDs and check
the analytics capture method directly (`env['southbrook.order.analytics'].
capture(order)` in a shell) to see the exception. Often the cause is
a non-kitchen order in `state = sale` that the capture method wasn't
written for — a domain narrowing on `order_line.product_id.categ_id`
is the right fix.

---

## Cron 4 — `cron_weekly_planning_baseline`

**Name in UI:** Southbrook: Weekly Planning Baseline
**Fires:** every 7 days, staggered to Sunday at ~02:00 local time
**Model:** `mrp.planning.run`
**Method:** `model._cron_baseline()`
**xml_id:** `southbrook_premium_orchestration.cron_weekly_planning_baseline`

**What it does.** Creates and runs a fresh `mrp.planning.run` record
as the weekly baseline. Idempotent within a 24h window — if a planning
run was created in the last day (by this cron or by a human), skips
and logs. After creating the record, calls `action_run()` on it if
the method exists; otherwise leaves it in draft for manual
inspection.

**What it reads.** Current open sale.orders, current MO backlog,
workcenter capacity, install due dates. The underlying OpenValue
planning engine does the heavy lifting; this cron is a thin
"schedule a baseline weekly" wrapper.

**What it writes.** One new `mrp.planning.run` record per week.
Downstream, `mrp.planning.run.line_ids` carry per-MO scheduling
decisions.

**Who cares.** The planner — Monday morning, you open the latest
planning run and use it as the starting point for the week. Without
this cron the only baseline is the last one a human created; over
time that drifts.

**Reading its last run.** Open **Manufacturing -> Planning -> Planning
Runs** (path provided by the OpenValue addon). The most recent record
is what this cron created. The run record carries `state` (draft /
done / error) and a chatter showing whether `action_run` succeeded.

**What to do if it errored.** Two failure modes: (a) the `create()`
failed — logged as WARNING, the cron exits and retries next week;
(b) the `action_run` failed — the planning run record exists in
`draft` state with no lines. You can open it and run `action_run`
manually to debug. Common cause of action_run failure: a workcenter
without a calendar (`mrp.workcenter.resource_calendar_id` is False).
The cron's optional defaults (capacity_horizon_days=14,
include_sales_demand=True, multilevel=False) are probed via
`hasattr` so the cron stays installable even if the OpenValue addon
ships a minimal field set.

---

## Cron 5 — `cron_dq_nightly_dry_run`

**Name in UI:** Southbrook: Quality Dry-Run Nightly
**Fires:** every 1 day, staggered to ~03:00 local time
**Model:** `southbrook.project.data.quality.report`
**Method:** `model._cron_nightly_dry_run()`
**xml_id:** `southbrook_premium_orchestration.cron_dq_nightly_dry_run`

**What it does.** Walks every active `project.project` record, scores
it against six data-quality dimensions, and writes one report with
finding lines per project. The six dimensions:

- `data_completeness` — % of confirmed SOs whose project.task link is populated
- `cabinet_specs` — % of project tasks with door_style + wood_species + finish set
- `mrp_link` — % of project tasks that have at least one linked MO
- `production_release` — % of tasks whose release state is not `blocked`
- `tool_lifecycle` — % of in-service tool assets with adequate remaining life
- `eco_freshness` — penalised by count of open ECOs > 30 days old

Each dimension produces a 0-100 score banded as `info` (>=90),
`warning` (>=70), `blocker` (<70).

**What it reads.** Sale orders, project tasks, MOs, tool assets,
ECOs — pretty much everything. Cheapest cron of the six is this is
NOT (it's the most data-touch-heavy), which is why it's pinned to
03:00 after the nightly logrotate window completes at 03:30.

**What it writes.** One `southbrook.project.data.quality.report`
record per active project per night, with one
`southbrook.project.data.quality.line` per dimension. (TransientModel
means these auto-vacuum after Odoo's default retention, so this isn't
a database bloat concern.)

**Who cares.** The PM / sysadmin (Course 7). Planner cares only
because a low DQ score on a project the planner owns means the
planner has been letting upstream data slide. If `cabinet_specs` is
the failing dimension on three of your jobs, you've been releasing
without door style on file — that becomes a wrong-finish problem at
the booth two weeks later.

**Reading its last run.** Open the model directly:
**Settings -> Technical -> Models -> southbrook.project.data.quality.report**
-> view records. Filter by `create_date >= today`. The summary field
shows the per-dimension scores in plaintext; the line_ids show the
findings. As a TransientModel these don't appear in the main menu —
they're meant to be read programmatically or surfaced by a wizard.

**What to do if it errored.** Per-project error isolation — one
project's failure is logged to `ir.logging` with `level=WARNING` and
the cron continues. The most common failure is a project with a
custom field expected by one of the scorers being absent
(`_score_dimension_*` methods all probe `_fields` and skip cleanly
when a column is missing). If the cron is producing many WARNINGs,
check `ir.logging` filtered by `path = ...data_quality_report` for
the actual exception text.

---

## Cron 6 — `cron_propose_eco_for_high_freq_overrides`

**Name in UI:** Southbrook: Propose ECOs for High-Frequency Cut-Spec Overrides
**Fires:** every 1 day, staggered to ~04:00 local time
**Model:** `southbrook.cut.spec.override`
**Method:** `model._cron_propose_eco_for_high_frequency_overrides()`
**xml_id:** `southbrook_premium_orchestration.cron_propose_eco_for_high_freq_overrides`

**What it does.** Aggregates `southbrook.cut.spec.override` records
over the last 90 days by `rule_key`. For any rule that was overridden
in 10+ work orders with no open ECO already referencing it, drafts
a new ECO (type "Construction-Rule Change") with the override count
and 5 sample overrides as evidence. Backlinks the sample overrides
to the new ECO via `eco_proposed_id`.

**What it reads.** `southbrook.cut.spec.override` records (the
operator-recorded deviations from default cut specs), the
`southbrook.eco` and `southbrook.eco.type` models.

**What it writes.** Zero, one, or more `southbrook.eco` records in
`state = open`. Updates `eco_proposed_id` on the sample overrides
that contributed evidence.

**Who cares.** The PLM engineer (Course 4) — they wake up to a queue
of auto-proposed ECOs every morning, each one saying "the shop floor
overrode this rule N times last quarter; should the default change?"
For the planner, only indirectly — an accepted ECO changes the
default cut spec, which changes how every subsequent MO routes.

**Reading its last run.** Open **PLM -> Engineering Change Orders**.
Filter by `state = open` and sort by `create_date desc`. ECOs whose
description starts with the cron's signature
(`<p>Rule <code>...</code> was overridden in <strong>N</strong>
work orders...`) and ends with `<em>Auto-proposed by
southbrook_premium_orchestration.</em>` are this cron's output.

**What to do if it errored.** Most common: no ECO type matching
"Construction-Rule Change" exists in the database. The cron logs a
WARNING and exits clean — no ECOs proposed. Recovery: open
**PLM -> Configuration -> ECO Types**, create a type named exactly
"Construction-Rule Change", and the next run picks it up. The
second-most-common failure is the override threshold being too
high — if your shop is small, 10 overrides per quarter for a single
rule is too high; consider tuning `threshold_pct` and the
minimum-count constant by calling the method manually with a
lower threshold to test.

---

## Your daily flow

**For the planner — start of day (5 min):**

- Open **Kitchen Ops -> MI Engine Status**. Check `last_run_at` is
  within the last hour. If it's older, the MI refire cron stalled —
  flag the sysadmin.
- Open **Kitchen Ops -> Kitchen Jobs**. Scan for chatter flips from
  the readiness cron overnight (`Decision: ready -> blocked`). For
  each, click in and read the chatter to see what tripped.
- Open **Kitchen Ops -> Production Release Queue**. Anything new
  here vs yesterday came from the MI gate refire — a previously
  green release that flipped.

**For the sysadmin — weekly (Monday 09:00):**

- Open **Settings -> Technical -> Scheduled Actions**, filter
  `Southbrook:`. Read the `Last Run` column. Six rows, all green,
  none stuck.
- Spot-check the cron 5 (Quality Dry-Run) output — open one report
  from over the weekend, look at the summary, ensure scores are
  trending up not down.
- Spot-check cron 6 (ECO Proposals) — open PLM, count open ECOs
  with the auto-proposed signature. If the count is growing
  unbounded, the PLM engineer isn't triaging; nudge them.

**On a failed cron (either role):**

1. Open Scheduled Actions, find the failing one. Read the `nextcall`
   date — if it's in the past, the previous tick crashed.
2. Click **Run Manually**. Watch the spinner. If it fails immediately,
   the popup shows the exception.
3. Open **Settings -> Technical -> Logging**, filter by the model name
   from the cron's code. The most recent WARNING line has the
   specific failure.
4. Fix the underlying issue. Run manually again to confirm green. The
   cron resumes its normal cadence on the next tick.

## Common mistakes + how to recover

**"The MI engine `last_run_at` shows 14 hours ago — did the cron
stop?"**

Open the cron record (Scheduled Actions). If `nextcall` is in the
future and `active = True` but the last run was 14 hours ago, the
worker that should run it is the cron worker, not a web worker.
On QNAP containers, the cron worker can hang on a long-running
psql query — check the Odoo container log for `cron` warnings.
Restart the container as a last resort; the cron's `nextcall` is
preserved so it picks up where it left off.

**"I see a chatter note saying readiness went from ready -> blocked
but I can't tell what changed."**

The readiness cron only logs the decision flip, not the underlying
sub-signal that caused it. Open the task, scroll down to the
readiness-lines breakdown. The sub-signal whose value flipped to
False between yesterday and today is the cause. Most common: the
nightly cron 5 (DQ) flagged a missing spec field which downstream
invalidates BoM Verified.

**"Cron 6 hasn't proposed an ECO in three weeks but I know the shop
is overriding the depth-to-drawer-count rule constantly."**

Two likely causes. (a) The override count is below the 10-per-90-day
floor — small shop, infrequent rule. (b) An open ECO already
references that rule_key — the cron skips a rule that already has
one open. Open ECOs filtered by description containing
`depth_to_drawer_count`. If one exists, close it (accept or reject)
to unblock future proposals.

**"The DQ dry-run is creating massive reports — disk space concern?"**

It shouldn't. The DQ report is a `TransientModel` — Odoo auto-vacuum
prunes it on the standard retention schedule. If it's growing
unbounded, check `ir.config_parameter` for
`base.partner_autocomplete_insufficient_credit` or similar (legacy
setting that can disable transient cleanup). The real fix is to
ensure the transient.autovacuum cron is enabled in the upstream
mail/base modules.

**"The weekly planning baseline cron created a run but `action_run`
errored. The run sits in draft."**

Open the run record. The chatter has the exception. Most common
cause is a workcenter without a resource calendar
(`mrp.workcenter.resource_calendar_id = False`). Fix the workcenter
(set the calendar to the company's default working hours), then
open the run and click **Run** manually. The cron's only job is
to create + kick off the run; once the run exists, the human can
drive it to completion.

## What the system is doing behind the scenes

All six crons live in `southbrook_premium_orchestration` and are
seeded by data XML files (`data/ir_cron.xml` + `data/eco_proposal_cron.xml`).
The seed files use `noupdate="0"` so a `-u
southbrook_premium_orchestration` re-creates anything an admin
archived — they're the authoritative source. The crons reference
their target model by `model_id` (via `ref="model_..."`), which is
why the model must exist at install time.

Each cron is owned by `base.user_root` and runs with full
system privileges. The `state = code` field means the cron's body is
inline Python (`model._cron_name()`) — not a server action with a
chain. This is intentional: makes the call stack trivially debuggable
(the method is in a tracked Python file).

The crons stagger their first run after install using the `nextcall`
field with `eval` expressions that add 2-10 minutes from
`DateTime.now()`. This avoids a thundering-herd on a 2G Odoo
container. After the first run, each cron's `nextcall` is driven
by `interval_number` + `interval_type`.

The MI engine state singleton (cron 2's record) is a stored model
in this addon (`southbrook_premium_orchestration/models/
southbrook_mi_engine.py`) that exists specifically because Odoo 19
forbids inheriting an `AbstractModel` as a `Model` — the parent
`southbrook.mi.engine` AbstractModel from the manufacturing
intelligence addon stays abstract, and we add a sibling stored
`southbrook.mi.engine.state` for the telemetry. The cron calls the
abstract parent's `_cron_refire_gates` via env.

Defensive coding throughout: every cron probes `_fields` containment
before referencing custom fields (because the live database has UI-
declared fields that fresh CE databases don't), tries multiple
method-name variants for migration tolerance, and per-record
try/except around side-effecting calls so a single bad row doesn't
stall the sweep. The result is that every cron stays green even on
half-migrated environments.

## Quiz (5 questions, applied)

**1.** You open Kitchen Jobs at 08:00 and see five jobs that were
green at 17:00 yesterday now showing `readiness = blocked`. The
chatter on each says the same: "Decision: ready -> blocked." Which
cron caused this, and what's the most likely upstream cause?

> Cron 1 (Recompute Project Readiness, every 30 minutes) ran
> overnight and flipped the decision based on a re-evaluated
> sub-signal. Five jobs flipping simultaneously suggests a shared
> upstream — most likely cron 5 (Quality Dry-Run, nightly ~03:00)
> raised a DQ finding that downstream invalidated one of the
> readiness sub-signals (BoM Verified or Crew Reserved). Open one
> of the tasks, look at the readiness lines breakdown, find the
> False sub-signal — that's the actual cause.

**2.** The sysadmin asks why the order analytics backfill cron
(cron 3) is doing nothing — `last_run` is recent but no INFO lines
in the log. What's the explanation?

> The cron's INFO line on a clean run reads "no unscored orders,
> all confirmed orders already captured" — meaning every confirmed
> SO already has its analytics row. That's the steady state: this
> cron is a SAFETY NET for orders that bypassed the always-on
> `action_confirm` capture (the bypass mode is rare). If no orders
> are escaping the realtime capture, the cron's job is to confirm
> "nothing to do" and exit. That's healthy, not broken.

**3.** A planner asks "why does the MI Engine Status board show
last_run_check_count = 0?" What does this mean, and how do you
diagnose?

> The cron 2 fired but found zero gate checks. Either (a) no
> `southbrook.mi.check` records have `is_gate = True`, or (b) no
> MOs are in `confirmed` / `progress` state. Probe both: in a
> shell, `env['southbrook.mi.check'].search_count([('is_gate','=',True)])`
> and `env['mrp.production'].search_count([('state','in',('confirmed',
> 'progress'))])`. If the first is zero, gate checks haven't been
> seeded; that's a configuration gap, not a cron failure.

**4.** The PLM engineer says "I've gotten three auto-proposed ECOs
this month for the `width_to_door_count` rule. They're all redundant —
can I tune the cron to be less aggressive?"

> Yes — the cron threshold is in
> `_cron_propose_eco_for_high_frequency_overrides(window_days=90,
> threshold_pct=50.0)` and the minimum-count floor is 10 inside the
> method. The aggressive symptom is that the engineer closed the
> previous ECO (which would have suppressed re-proposal — the cron
> filters out rules with an open ECO) before fixing the underlying
> rule. Either keep the previous ECO open until the rule changes,
> or have the engineer set its state to "accepted-but-deferred" so
> the cron's `domain = [('state','=','open')]` skips it.

**5.** The weekly planning baseline cron (cron 4) created a run
last Sunday but it's stuck in `draft`. The chatter says
`action_run` raised "Workcenter ENG01 has no resource_calendar_id."
What do you fix, and why is the cron's design resilient to this?

> Open the ENG01 workcenter, set `resource_calendar_id` to the
> company's default working schedule. The cron's design is
> resilient because (a) `create()` succeeded — the planning run
> record exists for a human to inspect, (b) `action_run` failed
> inside a try/except so the cron didn't crash and the next week's
> tick will try again, and (c) the cron's INFO log says the run is
> in draft for manual inspection. Once you fix ENG01's calendar
> and click **Run** on the existing run record, the planning
> completes. The cron has done its job — the human takes over for
> the recovery.

---

## What this lesson does NOT cover

- The shape of the Kitchen Jobs board and what readiness/release
  states mean -> lesson 2.1.
- The ENG01 release gate that the MI refire cron's gate checks
  feed into -> lesson 2.2.
- Bottleneck-aware scheduling against the workcenters whose loads
  the planning baseline cron computes -> lesson 2.3.
- Reading the MI report — the user-facing surface that this
  lesson's cron 2 populates -> lesson 2.5.
- Course 4 — how ECOs (raised by cron 6) get triaged, approved,
  and propagated into cut specs.
- Course 7 — sysadmin's deeper dive into cron 5 (DQ) and cron 4
  (planning baseline), including how to wire alerts when a cron
  goes red.
- Native Odoo `ir.cron` mechanics, the cron worker process, and
  scheduling internals -> Odoo's own training + the
  `transient.autovacuum` reference.
