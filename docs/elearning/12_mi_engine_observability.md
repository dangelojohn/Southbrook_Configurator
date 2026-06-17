---
course: 12 — Kitchen Ops Deep Dive
chapter: 12.6
title: MI Engine Status — The Planner's Observability Lens
duration: 30 minutes
audience: Production Planner + IT Admin (the two who read the singleton telemetry)
prereqs: Course 2 lessons 2.4 (Crons) + 2.5 (MI Reports). This lesson goes one layer deeper into the singleton state record.
custom_modules: southbrook_premium_orchestration, southbrook_manufacturing_intelligence
---

# MI Engine Status — The Planner's Observability Lens

## Who this lesson is for

You're the planner who walks in at 7am and wants a 30-second answer
to "is the MI engine running cleanly?" OR you're the IT admin who
got paged at 03:14 because something flipped overnight and you need
to confirm the cron's not the culprit. Course 2 lesson 2.4 covered
the cron mechanics from the sysadmin's perspective; lesson 2.5
covered the per-MO MI checks the planner acts on. THIS lesson is
the **singleton state record** that sits between them — the engine's
self-reported last-run telemetry.

The MI Engine Status board is a one-screen health dashboard. Get
comfortable with it and you'll stop chasing ghosts when the readiness
crons go quiet.

## Where this lives on the site

For the planner:

> **Kitchen Ops → MI Engine Status**

The singleton form on `southbrook.mi.engine.state`. Action
`action_mi_engine_status` in
`southbrook_premium_orchestration/views/mi_engine_views.xml`.

For the IT admin (cron-level diagnosis):

> **Settings → Technical → Scheduled Actions → "Southbrook: Refire MI
> Stage-Gate Checks"**

The cron record itself. From here you can see `nextcall`, `lastcall`
(approximate), `active`, and click **Run Manually** to fire
synchronously.

For the live MI checks the singleton's telemetry counted:

> **Settings → Technical → Models → southbrook.mi.check**

The flat record list. Filter by `is_gate = True` to see the rules
the cron evaluates against in-flight MOs.

## What your screen shows

The MI Engine Status form (only one record exists — singleton) has
two columns and a notice banner:

### Left column: Last Run

- **Last Run At** (`last_run_at`) — Datetime, readonly. Timestamp
  of the most recent `_cron_refire_gates` execution.
- **Last Run Duration (ms)** (`last_run_duration_ms`) — Integer,
  readonly. How long the last sweep took. Typical: 100-2000 ms for
  the Southbrook load.
- **Last Run Evaluations** (`last_run_check_count`) — Integer,
  readonly. The number of (MO × check) evaluations attempted.
  Equals `mo_in_flight_count × rule_count` if all combinations
  fired.
- **Last Run Blockers** (`last_run_blockers`) — Integer, readonly.
  How many evaluations returned `severity = blocker`.
- **Last Run Warnings** (`last_run_warnings`) — Integer, readonly.
  How many returned `severity = warning`.

### Right column: Current State

- **MOs In Flight** (`mo_in_flight_count`) — Integer, computed live.
  `mrp.production` count where `state in ('confirmed', 'progress')`.
- **Active Gate Rules** (`rule_count`) — Integer, computed live.
  `southbrook.mi.check` count where `is_gate = True` (or all rows
  if `is_gate` field doesn't exist).

### Header

- **Run Engine Now** button (`action_run_now`) — fires
  `_cron_refire_gates` synchronously and pops a notification with
  the result (or warning if any blockers).

### Notice banner

A blue info panel explaining that the MI engine refires every
active gate check against every in-flight MO on an hourly schedule,
and recommends Run Engine Now for immediate refire after rule
edits or new MO releases.

## How the planner reads this board (30 seconds)

The morning check:

1. **Is `Last Run At` within the last hour?**
   - Yes → cron is healthy. Move to step 2.
   - No → cron stalled. Page the IT admin (or follow the
     diagnosis path below if you're it).

2. **Is `Last Run Duration (ms)` typical for your load?**
   - <2000 ms → normal.
   - 2000-10000 ms → slow but functional; investigate at end of day.
   - >10000 ms → cron is grinding; almost certainly a regression in
     a check evaluator. Page the dev team.

3. **Is `Last Run Blockers` zero?**
   - Yes → no MO is currently failing a gate. Floor releases are
     clean.
   - No → at least one MO failed a gate check. Cross-reference with
     the Kitchen Jobs board (any cards in `release=blocked`?) and
     the per-MO MI Production Board (lesson 2.5).

4. **Does `Last Run Evaluations` ≈ `MOs In Flight × Active Gate
   Rules`?**
   - Yes (close to product) → every MO was evaluated against every
     rule. Healthy sweep.
   - Way less → some MOs or rules were skipped (likely error
     branches in the evaluator). Check `ir.logging` for warnings.
   - Way more → the evaluator is double-firing somehow. Unusual; dev
     investigation needed.

## How the IT admin reads this board (incident triage)

When something flipped overnight that shouldn't have:

1. **Confirm the cron ran.** `Last Run At` should be ≤1 hour ago.
2. **Confirm it counted things.** `Last Run Evaluations` > 0. If
   zero, either no MOs are in flight (check
   `mo_in_flight_count`) or no gate rules exist (check `rule_count`).
3. **Inspect the gate output.** If `Last Run Blockers > 0`, open
   the Kitchen Jobs board and find the affected MOs / tasks via the
   release queue (lesson 12.4). The chatter on each task will
   show "release state ready → blocked" with the timestamp.
4. **Compare to the prior tick.** The singleton stores only the
   LATEST run. To see the prior run's telemetry, check
   `ir.logging` (filter by model `southbrook.mi.engine.state` or
   keyword `MI engine refire`). The cron emits one INFO line per
   tick with the same summary numbers.

## The relationship to the six orchestration crons

Course 2 lesson 2.4 has the full cron schedule. The MI Engine
Status board surfaces ONE of the six crons specifically:

**Cron 2 — Southbrook: Refire MI Stage-Gate Checks** — every hour,
calls `southbrook.mi.engine.state._cron_refire_gates()`. This is
the cron whose telemetry the singleton stores.

The other five crons are NOT surfaced on this board:

- Cron 1 (Recompute Project Readiness) — telemetry is the
  `readiness_last_recomputed_at` stamp on each `project.task`.
- Cron 3 (Backfill Order Analytics) — telemetry is in
  `ir.logging`.
- Cron 4 (Weekly Planning Baseline) — telemetry is the new
  `mrp.planning.run` record's `create_date` + state.
- Cron 5 (Quality Dry-Run Nightly) — telemetry is one
  `southbrook.project.data.quality.report` per project per night.
- Cron 6 (Propose ECOs for High-Frequency Cut-Spec Overrides) —
  telemetry is the newly-created `southbrook.eco` records.

So the MI Engine Status board is NOT a one-stop overall health
panel — it's specifically the MI gate refire cron's panel. Other
crons need other observability paths.

## How to spot a stuck cron

The pattern:

- `Last Run At` is hours old.
- `MOs In Flight` is healthy (> 0).
- `Active Gate Rules` is healthy (> 0).
- The Kitchen Jobs board shows stale readiness decisions (cards
  still showing yesterday's state).

This means the cron isn't firing. Diagnosis:

1. Open **Settings → Technical → Scheduled Actions → Southbrook:
   Refire MI Stage-Gate Checks**.
2. Check `Active` is True. If False, someone disabled it — flip
   back on.
3. Check `Next Execution Date`. If it's in the past, the previous
   tick crashed and the cron is stuck waiting. Read the Odoo log
   for `cron` warnings around that timestamp.
4. Click **Run Manually**. If it fires cleanly, the cron is fine
   now and the previous failure was transient; the next scheduled
   tick will pick up.
5. If it errors immediately, the cron body has a regression. Read
   the popup exception text. Most common: a new MI check rule
   has a syntax error in its evaluator method. Find via
   `southbrook.mi.check` records modified recently; fix; re-run.

## How to manually re-fire the MI engine

From the MI Engine Status form:

1. Click the green **Run Engine Now** button in the header.
2. The form's `action_run_now` method calls `_cron_refire_gates()`
   synchronously and shows a notification: "Refired N evaluations
   in M ms (X blockers, Y warnings)." The notification is `success`
   if blockers == 0, otherwise `warning`.
3. The singleton fields update on save. Refresh the form to see
   the new `last_run_at` etc.

When to use Run Now:

- After editing or creating a gate rule (`southbrook.mi.check` with
  `is_gate = True`).
- After releasing a new MO to production (to confirm it passes the
  gate immediately rather than waiting for the next hourly tick).
- During incident response, to confirm a fix worked without
  waiting 60 minutes.

When NOT to use Run Now:

- On a slow shop (Run Now blocks the UI for the duration of the
  sweep). Use the scheduled cron and refresh the board after.
- Repeatedly to test a check (use a unit test against the
  evaluator directly instead).

## Your daily flow

**Planner (start of day, 1 min):**

1. Open Kitchen Ops → MI Engine Status.
2. Confirm Last Run At ≤ 1 hour ago.
3. Confirm Last Run Blockers == 0 (or note the count for triage).
4. Close the tab.

Done. This is a 60-second check. Everything else from MI lives on
the per-MO MI Production Board (Course 2 lesson 2.5).

**IT admin (weekly review):**

1. Open the board. Spot-check Last Run At is recent.
2. Open Settings → Technical → Scheduled Actions → filter
   "Southbrook:". All 6 cron rows should be green.
3. Open `ir.logging`, filter `model = southbrook.mi.engine.state`,
   last 7 days. Scan for WARNING lines. Each WARNING names a
   specific check that errored — over time these accumulate and
   indicate a check that needs maintenance.

**During an incident (planner OR admin):**

1. Open the board. Read all 7 fields.
2. If Run Engine Now is appropriate, click it and watch the
   notification.
3. Compare the post-run state to the pre-run state — did blockers
   drop? If yes, the issue is resolved. If no, the underlying
   data hasn't changed and the recommendation is to fix the
   upstream artifact (BoM, cutlist, etc).

## Common mistakes + how to recover

**"`Last Run At` is current but blockers is 47 and we have only 8
MOs in flight."**

The blocker count is `(MO × check)` evaluations that returned
blocker, not unique MOs. If you have 8 MOs and 6 gate rules and
all 8 MOs fail the same rule, blockers = 8. If they fail different
rules with overlap, it can climb. The number is signal strength,
not unique-MO count. To find unique MOs, open the MI Production
Board (lesson 2.5) filtered by `x_mi_status = blocked`.

**"The form shows `MOs In Flight = 0` but I just confirmed 5 MOs
ten minutes ago."**

The two right-column counts are LIVE computes (page-load time).
Refresh the form. If still 0, the MOs aren't in `confirmed` or
`progress` state — they're probably in `draft` or some other state
the cron doesn't count. Open the MOs and check the state.

**"`Active Gate Rules = 0` but the team configured rules last
week."**

Two causes. (a) The rules were created with `is_gate = False` (the
default). Open `southbrook.mi.check` records and flip `is_gate =
True` on the ones meant to gate. (b) The `is_gate` field doesn't
exist on the model (older version of MI). Verify by
`'is_gate' in env['southbrook.mi.check']._fields` in a shell. If
False, the cron falls back to counting all rules — but the count
would then be non-zero. If True and the count is zero, the rules
just aren't gates.

**"I clicked Run Engine Now and the page hangs."**

The synchronous run is taking too long. Either the sweep is
genuinely huge (hundreds of MOs × dozens of checks) or one check
evaluator is in an infinite loop. Wait 30 seconds; if still
hanging, kill the browser tab. The cron will recover; the next
scheduled tick fires normally. Page the dev team if it hangs every
time.

**"The notification says 'Refired 0 evaluations.' I have MOs in
flight."**

The MOs are in flight but the gate-rule query returned zero rules
(check `rule_count` on the form). With no rules to evaluate, the
sweep does nothing. Configure at least one rule with `is_gate =
True` to activate the cron's purpose.

## What the system is doing behind the scenes

The MI engine has TWO models, by design, because of a v19
constraint:

1. **`southbrook.mi.engine`** — AbstractModel defined in
   `southbrook_manufacturing_intelligence/models/mi_engine.py`.
   Holds the helper methods (cut summary, severity normalisation,
   per-package and per-MO recompute logic) used by other agents.
2. **`southbrook.mi.engine.state`** — concrete stored Model
   defined in
   `southbrook_premium_orchestration/models/southbrook_mi_engine.py`.
   Holds the singleton telemetry record and the
   `_cron_refire_gates` cron entry point.

Why two? Odoo 19 forbids `_inherit`-ing an AbstractModel as a
Model (the `AbstractModel inherit trap` documented in the QNAP
memory notes). The original design was to extend the abstract
parent to add `last_run_at` etc., but that raised `TypeError` at
registry load. The Phase 1 fix: keep the parent abstract for its
helpers, add a sibling stored model for the telemetry.

The cron config (`data/ir_cron.xml`):

```xml
<record id="cron_mi_engine_refire_gates" model="ir.cron">
    <field name="name">Southbrook: Refire MI Stage-Gate Checks</field>
    <field name="model_id" ref="model_southbrook_mi_engine_state"/>
    <field name="state">code</field>
    <field name="code">model._cron_refire_gates()</field>
    <field name="interval_number">1</field>
    <field name="interval_type">hours</field>
    <field name="user_id" ref="base.user_root"/>
</record>
```

`model._cron_refire_gates()` is the entry point. The implementation:

1. Time the start (millisecond precision).
2. Get / create the singleton via `_get_singleton`.
3. Search all MOs in `confirmed` / `progress`.
4. Search all gate checks (`is_gate = True`, with fallback to all
   if the field doesn't exist).
5. For each (MO × check) pair, call
   `_evaluate_check_against_mo`, which dispatches to whatever
   evaluator the check exposes (`_evaluate_against`,
   `_evaluate_for_mo`, or `evaluate`).
6. Normalise the return value to `blocker` / `warning` / other
   via `_severity_of`.
7. Count blockers and warnings.
8. **Wrap every evaluator call in try/except.** A single
   misbehaving check can't stall the sweep — it's logged WARNING
   with the check id, MO id, and exception text, and counted as
   a no-op.
9. Write the singleton with last_run_at, count, blockers, warnings,
   duration.
10. Log INFO with the summary.
11. Return the summary dict (for `action_run_now`'s notification).

The Run Engine Now button (`action_run_now`):

1. Ensure singleton.
2. Call `_cron_refire_gates()`.
3. Build a notification dict with the summary.
4. Return — Odoo displays the notification.

The notification severity is `success` if blockers == 0 else
`warning`. This is your visual feedback in the UI for "did Run
Now solve the problem?"

## Quiz (5 questions, applied)

**1.** You open MI Engine Status and see `Last Run At` is 4 hours
old, `MOs In Flight = 12`, `Active Gate Rules = 7`. What's the
diagnosis and recovery?

> The cron is stuck. Open Settings → Technical → Scheduled Actions
> → "Southbrook: Refire MI Stage-Gate Checks". Check Active is
> True. Check Next Execution Date — if it's in the past, the
> previous tick crashed. Click Run Manually to fire synchronously
> and watch for errors. If it succeeds, the cron resumes its
> normal hourly cadence. If it errors immediately, the popup
> shows the exception; check `ir.logging` for the matching
> WARNING line and fix the underlying cause.

**2.** A planner asks "the MI Engine Status shows zero blockers
but the Kitchen Jobs board has a card in `release=blocked`. Why?"

> The MI engine's blocker count is from `is_gate = True` checks
> against in-flight MOs (state `confirmed` / `progress`). The
> release state on the task is computed from FIVE different
> booleans + six data prerequisites (lesson 12.4). They're
> different gates. A task can be release=blocked because the
> install date is missing (no MI involvement) or because the
> engineer hasn't flipped CAD Approved. The MI engine isn't the
> only gate; it's one of several.

**3.** You click Run Engine Now and the notification says "Refired
14 evaluations in 230 ms (0 blockers, 2 warnings)." Walk through
what this tells you.

> 14 evaluations means 14 (MO × check) pairs were attempted.
> 230 ms is healthy. 0 blockers means no MO failed a hard gate.
> 2 warnings means 2 evaluations returned severity=warning —
> non-blocking concerns. To find them, open the MI Production
> Board (lesson 2.5), filter by `x_mi_warning_count > 0`. The 2
> warnings are surfaced there as `southbrook.mi.check` rows with
> severity=warning.

**4.** An admin notices the singleton form's `Last Run
Evaluations` keeps growing each tick (1000, 2000, 4000, 8000) but
`MOs In Flight` is constant at 50 and `Active Gate Rules` is
constant at 8. What's the diagnosis?

> 50 × 8 = 400 evaluations per tick is normal. Seeing 1000+ means
> the sweep is double-firing. Most likely cause: an evaluator
> method is recursing into the cron (calling
> `_cron_refire_gates` from inside itself, perhaps through a
> trigger). This is a code regression. Page the dev team; in the
> meantime disable the cron and Run Now manually for spot
> evaluations until fixed.

**5.** A planner asks "if I want to know how long the cron has
been broken, where do I look?"

> Two places. (1) `Last Run At` on the singleton shows the
> timestamp of the most recent successful tick — so the broken
> window started after that time. (2) `ir.logging` filtered by
> `model = southbrook.mi.engine.state` shows every tick's INFO
> line, including the broken ones (failures are WARNINGs).
> Combined, you can reconstruct the failure window: last
> successful INFO line, then a series of WARNINGs, then now. The
> singleton itself only stores the most recent SUCCESSFUL run.

---

## What this lesson does NOT cover

- The cron mechanics for all six orchestration crons (schedule,
  model, method, recovery) → Course 2 lesson 2.4 + Course 7
  lesson 7.1.
- The per-MO MI checks the planner triages (severity, category,
  recommendation) → Course 2 lesson 2.5.
- The Production Release Queue and the five engineer booleans →
  lesson 12.4 + Course 2 lesson 2.2.
- How an MI check fires a Hermes recommendation → Course 3 lesson
  3.2.
- Authoring new MI checks → developer-side, out of e-learning
  scope; refer to the MI engine source in
  `southbrook_manufacturing_intelligence/models/mi_engine.py`.
- Native Odoo `ir.cron` mechanics → Odoo's own documentation.
