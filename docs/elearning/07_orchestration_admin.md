---
course: 7 — Sysadmin
chapter: 7.1
title: Premium Orchestration — The Six Crons and How to Read Their Last-Run State
duration: 45 minutes
audience: IT Admin / Sysadmin who owns the Odoo 19 stack on QNAP and is on-call when a nightly cron misses
prereqs: Basic Odoo backend nav, comfort with the *Technical → Automation → Scheduled Actions* surface, SSH to the QNAP host
custom_modules: southbrook_premium_orchestration
---

# Premium Orchestration — The Six Crons and How to Read Their Last-Run State

## Who this lesson is for

You're the sysadmin on call when a Southbrook user opens a ticket saying
"the Kitchen Jobs board is stale" or "MI Status hasn't refreshed since
yesterday." Both are cron-driven surfaces. The `southbrook_premium_orchestration`
addon owns **six scheduled actions** that, together, keep the platform's
analytical / creative / practical loop alive. This lesson is how you find
them, read their last-run telemetry, manually re-fire one after a missed
window, and recover when one errors mid-run.

## Where this lives on the site

The six crons are seeded by the addon into Odoo's native scheduler. To
inspect them, sign in at **southbrookcabinetry.space/odoo** as a member of
the *Administration / Settings* group, then:

> **Settings → Technical → Automation → Scheduled Actions**

Filter the list by *Name* containing `Southbrook:` — you should see
**exactly six** records. If you see fewer than six, an admin has archived
one by hand; the addon re-seeds with `noupdate="0"` on every `-u` upgrade,
so re-running `docker exec southbrook-odoo odoo -u southbrook_premium_orchestration`
will restore any missing record.

For the MI engine's last-run telemetry specifically, the in-app view is:

> **Kitchen Ops → MI Status → Southbrook Manufacturing Intelligence**

That form shows the singleton state record (`southbrook.mi.engine.state`)
with `last_run_at`, `last_run_check_count`, `last_run_blockers`,
`last_run_warnings`, and `last_run_duration_ms` — the six-field telemetry
panel populated by the hourly refire cron.

For SSH-level inspection of cron output, the Odoo container log on the QNAP
is the source of truth:

> **`ssh admin@ssh.odooiq.com`** then
> **`docker logs southbrook-odoo --since 24h | grep -E "Southbrook:|cron"`**

## What your screen shows

The Scheduled Actions list view for the six Southbrook crons shows, per
row:

- **Name** (`name` on `ir.cron`) — the human-readable cron label, all
  prefixed `Southbrook:` so you can grep them out of the native Odoo
  cron noise.
- **Model** (`model_id` on `ir.cron`) — the model the cron's code runs
  against. Useful when you're tracing which model's `_cron_*` method
  fires.
- **Active** (`active` on `ir.cron`) — boolean. **All six must stay
  True.** If you see a row with Active = False, that cron has been
  manually disabled and the loop it belongs to is silently dark.
- **Next Execution Date** (`nextcall` on `ir.cron`) — the next time
  Odoo's scheduler will fire this cron. If `nextcall` is in the past
  by more than the cron's `interval`, the scheduler is backed up or
  the worker is wedged.
- **Interval** (`interval_number` + `interval_type`) — how often the
  cron is supposed to fire. The six Southbrook crons run on five
  distinct intervals: **30 min, 1 h, 6 h, daily, weekly**.
- **User** (`user_id`) — should be `OdooBot` (`base.user_root`) on
  every Southbrook cron. If it's a real human user, someone edited it
  by hand and the cron will fail the moment that human is archived.

The MI Engine form (Kitchen Ops → MI Status) adds runtime telemetry:

- **MOs In Flight** (`mo_in_flight_count` on `southbrook.mi.engine.state`)
  — computed live, count of MOs in state `confirmed` or `progress`.
- **Active Gate Rules** (`rule_count`) — computed live, count of
  `southbrook.mi.check` records with `is_gate = True`.
- **Last Run At** (`last_run_at`) — stamped by `_cron_refire_gates`
  every successful run. If this is older than 2 h on a live system,
  the MI refire cron is in trouble.
- **Last Run Duration (ms)** (`last_run_duration_ms`) — sanity check.
  Normal range is a few hundred ms on 1-50 in-flight MOs. If it's
  growing toward the 30-min cron window, that's your early signal to
  raise an issue against the MI engine team.

## The six crons in detail

The order below is the install order from `data/ir_cron.xml` plus the
phase-2 `data/eco_proposal_cron.xml`. Each subsection follows the same
shape: **what it does, schedule, what it reads, what it writes, where to
look on a missed run, recovery procedure.**

### Cron 1 — Recompute Project Readiness

- **Cron name** (verbatim from XML): `Southbrook: Recompute Project Readiness`
- **XML id**: `cron_recompute_readiness_all`
- **Model**: `project.task`
- **Code**: `model._cron_recompute_readiness_all()`
- **Schedule**: every **30 minutes**, first fire +2 min after install.
- **What it reads**: every open `project.task` carrying an
  `x_southbrook_sale_order_id` link (the orchestration spine), in any
  state other than done / cancelled.
- **What it writes**: for each task, snapshots `readiness_decision` and
  `southbrook_production_release_state`, runs the readiness recompute,
  stamps `readiness_last_recomputed_at` on the task, and posts a
  chatter note on any task whose readiness *flipped* (ready → blocked,
  blocked → ready, etc.). The Kitchen Jobs dashboard sorts by
  `readiness_last_recomputed_at desc` so a stale stamp shows up
  immediately.
- **Log signal**: search the Odoo container log for
  `Premium Orchestration: readiness recompute changed status` — that's
  the chatter-emit path. The cron itself doesn't log on success;
  successful runs are silent.
- **Common error mode**: a sibling addon (e.g. `southbrook_project_mrp`)
  drifts and removes a readiness compute method the cron calls via
  `_invoke_readiness_recompute`. The cron is **defensive** — it
  iterates a priority list of method names and silently no-ops if
  none exist. So the symptom is not a stack trace but a *quiet*
  cron where readiness flips stop appearing in chatter.
- **Recovery**: open *Settings → Technical → Automation → Scheduled
  Actions → Southbrook: Recompute Project Readiness*, click *Run
  Manually*. If the dashboard still doesn't refresh, the issue is
  upstream in `southbrook_project_mrp`; raise a ticket against that
  agent. **Do not** disable this cron — Kitchen Jobs goes dark.

### Cron 2 — Refire MI Stage-Gate Checks

- **Cron name** (verbatim): `Southbrook: Refire MI Stage-Gate Checks`
- **XML id**: `cron_mi_engine_refire_gates`
- **Model**: `southbrook.mi.engine.state`
- **Code**: `model._cron_refire_gates()`
- **Schedule**: every **1 hour**, first fire +5 min after install.
- **What it reads**: every `mrp.production` in state `confirmed` or
  `progress`, every `southbrook.mi.check` with `is_gate = True`. Runs
  each check against each MO — the (MO × check) cartesian product is
  bounded because gate checks are usually small.
- **What it writes**: the singleton `southbrook.mi.engine.state` row
  with `last_run_at`, `last_run_check_count`, `last_run_blockers`,
  `last_run_warnings`, `last_run_duration_ms`. Plus whatever side
  effects the individual checks have on `mrp.production` (typically
  toggling a `gate_pass` flag).
- **Log signal**: `MI engine refire: N MOs × M checks = X evaluations,
  B blockers, W warnings, D ms` is emitted on every successful run at
  INFO level.
- **Common error mode**: a misbehaving `southbrook.mi.check` raises an
  exception during evaluation. The cron catches per-check exceptions
  and logs `MI engine: evaluation of check <id> against MO <id> raised
  <error>; counted as a no-op.` It does **not** raise — the whole sweep
  finishes — but the warning tells you which check + MO to investigate.
- **Recovery**: search the log for `MI engine: evaluation of check` to
  find the offending check, open it in *Kitchen Ops → MI Status →
  Checks*, fix or temporarily disable (toggle `is_gate = False`). Then
  *Run Manually* the cron. The button **Run Now** on the MI Engine
  form does the same thing and reports the dict back via a notification
  toast — preferable to the bare scheduler trigger because you get the
  evaluations/blockers/warnings summary inline.

### Cron 3 — Backfill Order Analytics

- **Cron name** (verbatim): `Southbrook: Backfill Order Analytics`
- **XML id**: `cron_backfill_order_analytics`
- **Model**: `southbrook.order.analytics`
- **Code**: `model._cron_backfill_unscored()`
- **Schedule**: every **6 hours**, first fire +10 min after install.
- **What it reads**: a raw SQL `LEFT JOIN` between `sale_order` (state
  = `sale`) and `southbrook_order_analytics`, fetching `sale.order.id`
  rows that don't yet have an analytics row. Avoids pulling the full
  analytics table into Python.
- **What it writes**: one new `southbrook.order.analytics` row per
  unscored confirmed sale order via the existing idempotent
  `capture(order)` method. Per-order failures are caught and logged
  with `Southbrook analytics backfill: capture failed for sale.order
  <id> (<exc>) — skipping.` so one bad order doesn't poison the sweep.
- **Log signal**: `Southbrook analytics backfill: N unscored confirmed
  orders found, capturing…` then `captured N / M unscored orders.` —
  the N over M tells you how many failed (M - N).
- **Common error mode**: `capture()` raises because a downstream model
  (`product_configurator_mrp` BoM, or `southbrook_estimating`'s pricelist
  resolver) drifted. The capture itself is owned by
  `southbrook_estimating` — this cron is just discovery + dispatch.
- **Recovery**: confirm the log line shows `captured 0 / N` (vs N / N
  on a healthy run). If 0 / N, *Run Manually* once to confirm the
  failure is reproducible; if it is, raise a ticket against
  `southbrook_estimating.southbrook.order.analytics.capture`. The
  cron will keep re-trying every 6 hours and self-heals automatically
  once the upstream is fixed.

### Cron 4 — Weekly Planning Baseline

- **Cron name** (verbatim): `Southbrook: Weekly Planning Baseline`
- **XML id**: `cron_weekly_planning_baseline`
- **Model**: `mrp.planning.run`
- **Code**: `model._cron_baseline()`
- **Schedule**: every **7 days**. `nextcall` is computed at install
  time to land on the next upcoming **Sunday 02:00** local time.
- **What it reads**: existing `mrp.planning.run` records from the last
  24 hours (de-dup guard).
- **What it writes**: a single new `mrp.planning.run` record with
  `date = today` and, where the OpenValue layer is present,
  `capacity_horizon_days = 14`, `include_sales_demand = True`,
  `multilevel = False`. Then calls `run.action_run()` if available.
- **Log signal**: `Southbrook planning baseline: run <name> exists
  within 24h window, skipping.` on a duplicate guard, or
  `Southbrook planning baseline: action_run failed on <run> (<exc>)
  — leaving run in draft for manual inspection.` on a failure.
- **Common error mode**: `action_run()` fails because the OpenValue
  engine hit a workcenter capacity edge case. The cron leaves the
  draft run in place so you can re-trigger it manually after the
  fix — it does **not** roll back the create.
- **Recovery**: open *Manufacturing → Planning → Planning Runs*, find
  the draft run with today's date, open it, click *Run* manually. If
  the OpenValue engine raises a useful exception you'll see it in the
  flash message; otherwise the Odoo log is the next stop. **Do not**
  delete the draft and re-run the cron — it will be skipped by the
  24-hour de-dup guard.

### Cron 5 — Quality Dry-Run Nightly

- **Cron name** (verbatim): `Southbrook: Quality Dry-Run Nightly`
- **XML id**: `cron_dq_nightly_dry_run`
- **Model**: `southbrook.project.data.quality.report`
- **Code**: `model._cron_nightly_dry_run()`
- **Schedule**: every **1 day**, `nextcall` lands at **03:00 local**
  (or the next 03:00 if installed after 03:00 today). Pairs with the
  QNAP logrotate window at 03:30 so heavy I/O lands after rotation
  completes.
- **What it reads**: every `project.project` with `active = True`.
- **What it writes**: one `southbrook.project.data.quality.report` row
  per active project, plus a scored line per DQ dimension on each. The
  cron returns the count of reports created. Per-project errors are
  written to `ir.logging` as warnings via the sudoed `_cron_nightly_dry_run`
  func tag — search `ir.logging` filtering by
  `func = _cron_nightly_dry_run` to see which projects failed without
  scrolling container logs.
- **Common error mode**: a project with a malformed BoM blows up the
  scoring of one dimension; the per-project exception handler swallows
  it and continues the fan-out. The report for that project is missing.
- **Recovery**: query the DQ report list filtered by today's date —
  any active project NOT in the list is a candidate. *Run Manually*
  on the cron, then re-check; if a specific project is still missing,
  open that project's BoMs and look for the `convert.py` complaint in
  the `ir.logging` warning text.

### Cron 6 — Propose ECOs for High-Frequency Cut-Spec Overrides

- **Cron name** (verbatim): `Southbrook: Propose ECOs for High-Frequency Cut-Spec Overrides`
- **XML id**: `cron_propose_eco_for_high_freq_overrides`
- **Model**: `southbrook.cut.spec.override`
- **Code**: `model._cron_propose_eco_for_high_frequency_overrides()`
- **Schedule**: every **1 day**, `nextcall` lands at **04:00 local** the
  day after install (so it runs after the DQ dry-run at 03:00 in cron 5).
- **What it reads**: `read_group` over `southbrook.cut.spec.override`
  records from the last `window_days = 90` days, grouped by `rule_key`.
- **What it writes**: for each `rule_key` with ≥ 10 overrides in 90
  days and no existing open ECO referencing it, creates one new
  `southbrook.eco` of type *Construction-Rule Change* with HTML
  description listing the 5 most recent sample overrides. Back-links
  each sample override via `eco_proposed_id` so the engineer reviewing
  the ECO can see the evidence.
- **Log signal**: `No Construction-Rule Change ECO type found; skipping
  ECO proposal sweep.` is the bootstrap-gap signal — the addon expects
  an ECO type seeded by `southbrook_plm`. Otherwise the cron is silent
  on success.
- **Common error mode**: the *Construction-Rule Change* ECO type is
  missing because the PLM module wasn't installed before Premium
  Orchestration. The cron logs the warning above and exits clean.
- **Recovery**: install / re-install `southbrook_plm`, then *Run
  Manually*. Result is a `{'proposed': N}` dict — N is the number of
  ECOs auto-drafted.

## Daily / Weekly / On-call

**Daily (5 min, before standup):**

- Open *Settings → Technical → Automation → Scheduled Actions*, filter
  `Southbrook:`. Confirm **all six** rows show *Active = True* and
  *Next Execution Date* in the future, not the past.
- Open *Kitchen Ops → MI Status*. Confirm *Last Run At* is within the
  last 2 h and *Last Run Duration (ms)* is under ~5,000.

**Weekly (Monday morning):**

- Open *Manufacturing → Planning → Planning Runs*. Confirm a fresh run
  exists from the previous Sunday 02:00 ± 1 h. If it's missing or in
  draft (didn't `action_run`), see cron 4 recovery.
- Open the DQ Report list, filter to the last 7 days, confirm there's
  one row per active project per day. Gaps indicate cron 5 misses.

**On-call (incident triggered by a user ticket):**

1. Identify which surface the user is complaining about (Kitchen Jobs,
   MI Status, Order Analytics, Planning, DQ, or ECO queue).
2. Map it to its cron via the table above.
3. Open the cron, check *Next Execution Date* vs *Now*.
4. If *Next Execution Date* is in the past by more than one interval,
   the Odoo scheduler is backed up — `docker logs southbrook-odoo
   --tail 200` for the master cron-runner heartbeat.
5. If the cron is firing but doing nothing, search the container log
   for the log signals listed above.
6. *Run Manually* once you've isolated the root cause — never as the
   first action.

## Common mistakes + how to recover

**"A user archived a cron because it looked spammy and now the dashboard
is dark."**

Re-seed via `docker exec southbrook-odoo odoo -u southbrook_premium_orchestration
-d southbrook --stop-after-init` from the QNAP host. The `noupdate="0"`
flag on the data XML re-creates any cron that's been deleted; archived
records get re-activated by the same load (active is in the data record).
**Don't** un-archive by hand and assume that's enough — the user may have
edited intervals or `user_id` too.

**"The MI refire cron is firing on schedule but Last Run At isn't
updating."**

The model `southbrook.mi.engine.state` is a singleton. If two singletons
ever get created (e.g. by a botched data migration), the cron writes to
one and your form view reads the other. Check with
`docker exec southbrook-odoo odoo shell -d southbrook -c
'self.env["southbrook.mi.engine.state"].search_count([])'` — answer must
be **1**. If it's > 1, keep the one with the most recent `last_run_at`
and unlink the others.

**"I ran the weekly planning cron manually and now there are two
planning runs from this week."**

The de-dup guard skips creates within a 24-hour window, but if the
scheduled run already happened and you manually fired again later, you
get one scheduled + one manual. The scheduler doesn't double-count;
either run is valid. Pick the one you trust (typically the manual one
since you ran it after fixing the issue) and archive the other from
*Manufacturing → Planning → Planning Runs*.

**"The ECO proposal cron is creating duplicate ECOs."**

It isn't — by design. The guard is `Eco.search([('state', '=', 'open'),
('eco_type_id', '=', rule_change_type.id), ('description', 'ilike',
rk)])`. If you see what looks like a duplicate, the prior ECO was moved
to a non-`open` state (probably `closed` or `done`) and the cron treats
it as resolved. That's the correct behaviour: a closed ECO does not
suppress new evidence.

**"Container restart and now Next Execution Date is in the past for
all six crons."**

That's normal — Odoo's scheduler catches up by firing each overdue cron
once on next worker tick. Confirm by watching `docker logs
southbrook-odoo --follow` for 2-3 minutes after the container is up. If
nothing fires, the cron-runner thread isn't healthy — restart the
container (`docker restart southbrook-odoo`) and watch for the
`Cron-runner` startup line.

## What the system is doing behind the scenes

Odoo's native `ir.cron` model owns the scheduler loop — one of the Odoo
worker threads polls `ir.cron WHERE active = True AND nextcall <= NOW()`,
acquires a row-level Postgres lock per row to prevent parallel workers
from double-firing the same cron, executes the `code` field as a Python
expression with `model` bound to the model named by `model_id`, and
advances `nextcall` by `interval`. Every cron the Premium Orchestration
addon ships is `state = code` (vs the deprecated `state = code_exec`
variant) and references its method via `model._cron_*()` — never a free
function.

The de-dup guards (24-hour window on the planning baseline, "existing
open ECO" search on the ECO proposer) are application-level idempotency
defenses, layered on top of Odoo's row-lock so that even a manually
triggered run inside the scheduled-window doesn't double-create. This
is why `Run Manually` is safe to use as your first recovery action
once you've isolated the root cause — the worst case is a no-op.

The `_cron_*` methods are all written to be **best-effort, non-raising**:
they catch per-record exceptions and log warnings rather than propagate
to the scheduler. The scheduler treats a raised exception as a failed
run and the row stays at the same `nextcall`, leading to tight retry
loops. Premium Orchestration's pattern of per-record `try/except` + log
+ continue is deliberate; if you find yourself adding bare `raise` to
one of these methods, you're breaking the contract.

## Quiz (5 questions, applied)

**1.** A user opens a ticket: "Kitchen Jobs board hasn't shown new
readiness flips since 9 AM." It's now 11 AM. Walk to the surface and
the chain of checks — what do you look at first?

> *Settings → Technical → Automation → Scheduled Actions*, filter
> `Southbrook:`. Find *Recompute Project Readiness*, check
> *Next Execution Date*. If it's in the past by more than 30 min,
> the scheduler is wedged — check `docker logs southbrook-odoo` for
> cron-runner activity. If `Next Execution Date` is in the future,
> the cron fired but the readiness recompute itself is silent —
> click *Run Manually* and watch the container log for the chatter
> emit line `Premium Orchestration: readiness recompute changed
> status`. No emit means no flips happened, which is consistent
> with the user's complaint but not a bug.

**2.** The MI Engine form shows *Last Run Duration (ms) = 28,400*
where it was 380 ms a week ago. Cron interval is 1 hour. What's the
risk and what do you do?

> Risk: the cron is approaching the 1-hour budget and at the
> current growth rate will exceed it within weeks, at which point
> runs overlap and the next run's `nextcall` advancement gets out
> of sync. Action: look at *MOs In Flight* — if it's spiked (e.g.
> 200+ vs the historical 20-30), the cartesian product (MOs × checks)
> is the cause. Talk to the production manager about closing finished
> MOs that lingered in `progress`. Don't change the cron interval —
> the fix is upstream.

**3.** You ran `docker exec southbrook-odoo odoo -u
southbrook_premium_orchestration -d southbrook --stop-after-init` during
a maintenance window. The container is back up and a user reports the
MI Status page now shows `Last Run At` as "yesterday". What happened?

> The MI engine singleton's stamp persists across the upgrade (it's
> a stored field on `southbrook.mi.engine.state`). The hourly refire
> cron's `nextcall` was advanced past the maintenance window, so it
> hasn't fired yet post-restart. Wait for the next scheduled fire,
> or *Run Manually* if the user needs the dashboard immediately —
> the *Run Now* button on the MI Engine form is the cleanest path
> because it reports the per-run summary inline.

**4.** The weekly planning baseline cron's last run is logged as
`action_run failed on Planning-2026-06-15 (Capacity exceeded on
SB-EDGE) — leaving run in draft for manual inspection.` What's the
right recovery sequence?

> Don't re-fire the cron — the 24h de-dup guard will skip and you'll
> chase your tail. Open *Manufacturing → Planning → Planning Runs*,
> find the draft `Planning-2026-06-15`, open it. The capacity exception
> means a workcenter is over-allocated; either reschedule the
> conflicting MOs upstream or adjust the workcenter's capacity for
> the planning window, then click *Run* on the draft directly. The
> next scheduled cron fire (next Sunday 02:00) will be a fresh run.

**5.** The ECO proposal cron logs `No Construction-Rule Change ECO type
found; skipping ECO proposal sweep.` every night for a week. Engineers
ask "are we missing override-driven ECOs?" — what's the answer and the
fix?

> Yes, the cron has been a no-op all week. The *Construction-Rule
> Change* ECO type is seeded by `southbrook_plm`. Either the PLM
> module isn't installed, or its seed data ran before the type
> existed. Check `southbrook.eco.type` for any row whose name matches
> `%Construction-Rule Change%` or `%rule%` — the cron's lookup is
> `ilike` and tolerant of label variants. If absent, install
> `southbrook_plm`, then *Run Manually* on the proposal cron; the
> return dict `{'proposed': N}` tells you how many ECOs were drafted
> across the last 90 days of overrides.

---

## What this lesson does NOT cover

- The QNAP-level cron (`backup-odoo.sh` at 03:00) and how to verify
  artifacts landed → **lesson 7.2 (Backups)**.
- The external Hermes Console queue at `hermes.odooiq.com` and how
  approved sysadmin recommendations get applied → **lesson 7.3
  (Hermes Console)**.
- The Production Planner's view of these crons (when to use the
  Production Release Queue vs *Run Manually*) → lesson 2.4.
- The MI dashboard from the floor manager's perspective (interpreting
  blockers vs warnings) → lesson 3.1.
- Generic Odoo `ir.cron` mechanics (de-dup locking, worker tick) →
  Odoo's own platform docs.
