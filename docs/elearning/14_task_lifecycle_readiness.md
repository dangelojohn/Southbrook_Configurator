---
course: 14 — Project Module Deep Dive
chapter: 14.3
title: Task Lifecycle + Readiness Compute — How "Ready" Is Calculated
duration: 35 minutes
audience: Project Manager + Production Planner (anyone who reads readiness to triage the day)
prereqs: Lesson 14.1 (architecture); Course 2 lesson 2.2 (release gate); Course 12 lesson 12.4 (production release queue)
custom_modules: southbrook_project_mrp, southbrook_premium_orchestration, southbrook_project
---

# Task Lifecycle + Readiness Compute — How "Ready" Is Calculated

## Who this lesson is for

You're the planner who triages the queue every morning by skimming the
readiness badges (Ready / Review / Blocked / Info) and never quite
trusts them because nobody told you what they actually compute. Or
you're the PM who needs to defend "this job is blocked" to a sales
rep and wants to point at the *specific check* that says so. This
lesson is the algorithm, the inputs, the cron schedule, and the
recovery moves when a value is wrong.

Course 2's bottleneck lesson treats readiness as a primitive. Course
12's queue lesson treats it as a header. This lesson takes it apart.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo**.

> **/odoo/project → any project → any task** — opens the task form.
> The readiness state appears as a coloured badge near the header and
> in the "Readiness" smart button (count = number of readiness checks).

> **Kitchen Ops → Kitchen Jobs** (planner kanban) — cards are coloured
> by `readiness_decision` (`ready` / `review` / `blocked` / `info`),
> sorted by `readiness_last_recomputed_at` desc by default.

> **Settings → Technical → Scheduled Actions → Southbrook: Recompute
> Project Readiness** — the cron's admin page. Shows last run, next
> run, and any traceback if it errored.

> **(task form) → Readiness smart button** — opens the
> `southbrook.project.readiness.line` list filtered to this task.
> Each line is one check (Cabinet Specs, Production Release Checklist,
> MRP Link, Materials / Purchasing, Scheduling, Crew, Equipment, etc.)
> with status + severity + reason + evidence + recommended_action.

## What your screen shows

The readiness header on a task is driven by **four computed fields on
`project.task`** (all owned by `southbrook_project_mrp`):

- `readiness_decision` (Selection: ready / review / blocked / info) —
  the four-state badge. **Aliases the `manufacturing_readiness_state`
  underneath.** Set by `_compute_phase1_operational_context`.
- `readiness_score` (Integer 0–100) — a tighter triage number.
  Aliases `manufacturing_readiness_score`. Set by the same compute.
- `readiness_last_recomputed_at` (Datetime, owned by
  `southbrook_premium_orchestration`) — stamped on every cron tick.
- `job_at_risk` (Boolean) — a separate computed flag from
  `_compute_mrp_status`; means "this job is late or has a started MO
  that isn't fully reserved." Surfaces as the red "At risk" banner on
  the form and the "At risk" pill on the kanban card.

The score and decision come from the **underlying readiness compute**
which lives in `_compute_manufacturing_readiness` on `project.task`
(`southbrook_project_mrp/models/project_task.py`, ~line 1749). It is
the canonical source.

### The readiness algorithm — what gets checked

Each "gate" is one of 11 checks. Each check emits one of three
verdicts — READY / REVIEW / BLOCKED — that get bucketed into three
text summaries (`manufacturing_blocker_summary`,
`manufacturing_warning_summary`, `manufacturing_info_summary`) plus
the full chronological narrative in `manufacturing_waterfall_summary`.

| # | Gate                              | READY when…                                                 | REVIEW when…                                | BLOCKED when…                                |
|---|-----------------------------------|--------------------------------------------------------------|---------------------------------------------|----------------------------------------------|
| 1 | Data Completeness                 | `customer_id` AND `source_order_id` set                      | —                                           | either missing                               |
| 2 | Cabinet Specs                     | all 4 spec fields set (see below)                            | one or more missing                         | —                                            |
| 3 | Production Release Checklist      | `southbrook_production_release_state == 'ready'`             | —                                           | else (covers all the sub-checks in 14.4)     |
| 4 | MRP Link                          | `production_count > 0`                                       | —                                           | no linked MOs                                |
| 5 | Engineering / CAD                 | `job_cad_status` empty OR contains "done"                    | non-empty + no "done"                       | —                                            |
| 6 | Materials / Purchasing            | not material_at_risk AND no open procurement                 | not at risk but open procurement exists     | `material_at_risk == True`                   |
| 7 | Scheduling                        | `unscheduled_workorder_count == 0`                           | —                                           | any WOs without `date_start`                 |
| 8 | Crew                              | `crew_gap == False`                                          | any unassigned MO or WO                     | —                                            |
| 9 | Equipment / Tooling               | `equipment_blocked == False`                                 | —                                           | any open maintenance request                 |
| 10| Production Capacity               | not over capacity AND not job_at_risk                        | over capacity OR job_at_risk                | —                                            |
| 11| Delivery / Install                | `southbrook_install_readiness_state == 'ready'`              | install checklist incomplete                | —                                            |
| 12| Calculations                      | ≥1 `southbrook.mi.check` linked                              | —                                           | — (emits INFO, not blocker)                  |
| 13| PM Phase / Manufacturing Reality  | `stage_mo_divergence == False`                               | stage hints at production but no MO started | —                                            |

The 4 required cabinet specs (gate 2) are defined in the constant
`_REQUIRED_CABINET_SPEC_LABELS` at the top of `project_task.py`:

- `x_southbrook_material_species` (owner: `southbrook_project`)
- `x_southbrook_hardware_specs` (owner: `southbrook_project`)
- `southbrook_door_style` (owner: `southbrook_project_mrp`)
- `southbrook_finish` (owner: `southbrook_project_mrp`)

### How the decision rolls up

```
if any gate is BLOCKED:    decision = "blocked"
elif any gate is REVIEW:   decision = "review"
else:                       decision = "ready"
```

The `info` decision in the Selection is reserved for tasks with no
manufacturing context (e.g. a hand-created task with no SO link); the
canonical compute will return "ready" by default but
`_compute_phase1_operational_context` falls back to "info" if
`manufacturing_readiness_state` is unset.

### How the score rolls up

```
penalty = blockers × 25 + warnings × 10
score = max(0, min(100, 100 - penalty))

# Then apply caps — if specific blockers are present, score is
# clamped to the cap even if the linear math says higher:
caps:
  no production_count           →  40
  CAD status open               →  55
  material_at_risk              →  60
  unscheduled WOs               →  55
  equipment_blocked             →  65
  production_release != "ready" →  65
  no job_install_due            →  80

score = min(score, *caps_applied)
```

So a task with one blocker and one warning has a base score of
`100 - 25 - 10 = 65`. If the blocker is "no production_count", the
cap of 40 applies, and the final score is 40.

### When does the recompute run?

Three triggers:

1. **`@api.depends` recompute on read** — every time you read the
   field (open the form, query the API), the compute fires if any of
   ~20 dependencies changed since last evaluation. The deps are
   listed at the top of `_compute_manufacturing_readiness`:
   `production_count`, `job_cad_status`, `material_at_risk`,
   `procurement_count`, `unscheduled_workorder_count`, `crew_gap`,
   `equipment_blocked`, `workcenter_over_capacity`, `job_at_risk`,
   `job_risk_reason`, `job_install_due`,
   `manufacturing_calculation_count`, `stage_mo_divergence`,
   `stage_mo_note`, `customer_id`, `source_order_id`,
   `southbrook_specs_complete`, `southbrook_production_release_state`,
   `southbrook_production_release_reason`,
   `southbrook_install_readiness_state`,
   `southbrook_install_readiness_reason`.

2. **The 30-minute cron** —
   `southbrook_premium_orchestration.cron_recompute_readiness_all`
   fires `_cron_recompute_readiness_all` against every task with
   `x_southbrook_sale_order_id != False` AND `state not in
   (1_done, 1_canceled)`. For each, it calls
   `action_recompute_readiness_lines` (which writes
   `southbrook.project.readiness.line` rows for the smart-button
   drill-down), then stamps `readiness_last_recomputed_at` and posts
   a chatter note if `(readiness_decision, southbrook_production_release_state)`
   changed since last tick.

3. **Manual recompute** — the *Readiness* smart button on the task
   form (action `action_view_readiness_lines`) calls
   `action_recompute_readiness_lines` before opening the list. So
   every time you click in, you get fresh evidence.

### The at-risk flag — separate from readiness

`job_at_risk` (Boolean) on `project.task` is computed by
`_compute_mrp_status` (`southbrook_project_mrp/models/project_task.py`,
~line 624). It is True when *either*:

- A started MO (`state in ('confirmed', 'progress')`) is not
  fully reserved (`reservation_state != 'assigned'`), OR
- Any non-done MO has a `date_deadline` in the past
  (`m.date_deadline.date() < today`).

The reason string is `job_risk_reason`. The flag feeds into the
"Production Capacity" gate of the readiness compute — when
`job_at_risk == True`, that gate fires REVIEW, which contributes 10
points of penalty + a "review" decision overall (unless something
else already pushed decision to "blocked").

## Your daily flow

**Morning (10 min):**

1. Open **Kitchen Ops → Kitchen Jobs**. The kanban groups tasks by
   `readiness_decision`. **The "Blocked" lane is your day.**
2. For each card in Blocked, click it open. Click the *Readiness*
   smart button. The drill-down list shows you the **specific check
   that blocked it** with the recommended action.
3. Triage:
   - "Missing customer / source sales order" → bounce to the
     salesperson; this task shouldn't have been created.
   - "No linked manufacturing orders" → run the *Link MOs from Sale*
     action on the task (or wait for procurement to create them).
   - "Components available: waiting" → check the procurement smart
     button; chase the PO.
   - "Equipment blocked" → check Maintenance; clear the open request
     or reroute the WO.
   - "X work orders not scheduled" → click the WOs smart button and
     hit *Schedule* on each.

**Mid-day:**

- The cron fires every 30 min on the half-hour mark (with a
  +2-minute stagger from install — see lesson 14.1). Tasks whose
  decision flipped since the last run get a chatter note on them so
  the followers (typically the PM + salesperson) are notified.

**End of day:**

- Sort the Kitchen Jobs board by
  `readiness_last_recomputed_at` desc. The most-recently-recomputed
  tasks are the ones the cron has touched in the last hour. If a
  task hasn't been recomputed in >2 hours, something is wrong —
  check the cron's admin page.

## Common mistakes + how to recover

**"A task shows BLOCKED but I just fixed the thing it was complaining
about."**

You probably fixed the upstream condition but haven't read the task
form yet — the compute is `@api.depends`-gated, so it only re-fires
on read. Force a refresh: open the task form, OR wait for the next
cron tick (max 30 min). The cron also recomputes
`action_recompute_readiness_lines` which rebuilds the
`southbrook.project.readiness.line` rows the drill-down reads.

**"The cron stopped running."**

Check **Settings → Technical → Scheduled Actions → Southbrook:
Recompute Project Readiness**. If `nextcall` is in the past and
`active = True`, Odoo's scheduler is paused (look at server logs).
If `active = False`, someone archived it — re-enable. If you see a
traceback, the most common cause is a task with malformed data
(historically: a `date_deadline` being a string instead of a date —
fixed 2026-06-11, see lesson 14.1's mention of the FIX 1 commit).

**"`readiness_last_recomputed_at` is fresh but the decision still
looks wrong."**

The cron ran but the compute returned what it returned. Open the
*Readiness* smart-button drill-down — the reasons are explicit.
Common: a gate you thought was satisfied isn't (e.g., you set
`southbrook_release_cad_approved = True` but the
`southbrook_release_bom_verified` is still False, so the Production
Release Checklist gate still blocks). Lesson 14.4 has the full
checklist.

**"A task is `info` but I expected `ready`."**

`info` is the fallback. It means `manufacturing_readiness_state` was
None/empty when the alias compute fired. Triggers: the task has no
SO link (so no MOs, so no gates run meaningfully). The drill-down
will be sparse. Resolution: link the SO via
`x_southbrook_sale_order_id` or trigger the linkage from the SO side
(see lesson 14.5).

**"The score on two tasks is identical but one is Blocked and one is
Ready."**

The score's caps are independent of the linear penalty math, so a
"ready" task with no blockers can hit 80 (because `job_install_due`
is missing — cap of 80) while a "blocked" task with one blocker can
also hit 80 (one blocker = 75 base, no caps tighter). Resolution:
read the decision first, score second. Score is a tie-breaker, not
the headline.

**"I want to override readiness for a specific task — I know the BoM
isn't verified but I'm authorising it anyway."**

You can flip `southbrook_release_bom_verified = True` (or any of the
5 sign-off booleans — see lesson 14.4) by hand on the task form,
which un-blocks the Production Release Checklist gate. **It's
tracked** (the field has `tracking=True`) so the chatter logs who and
when. This is the operator-controlled escape hatch; the readiness
compute respects the booleans, it doesn't second-guess them.

## What the system is doing behind the scenes

The readiness algorithm is **fully deterministic** — no ML, no
heuristics, no "fuzzy" matches. Every gate's verdict is a direct
function of explicit data on linked records.

The 13 gates are evaluated in a fixed order (data → specs →
production release → MRP link → engineering → materials →
scheduling → crew → equipment → capacity → install → calculations →
stage coherence), and the gates' output is appended to four parallel
buffers (gates, blockers, warnings, infos). At the end:

```python
task.manufacturing_waterfall_summary = "\n".join(gates)
task.manufacturing_blocker_summary  = "\n".join(blockers) or "No start blockers."
task.manufacturing_warning_summary  = "\n".join(warnings) or "No manager-review warnings."
task.manufacturing_info_summary     = "\n".join(infos)    or "No efficiency prompts."
task.manufacturing_readiness_state  = "blocked" if blockers else ("review" if warnings else "ready")
```

The waterfall summary is what the planner reads end-to-end in the
"Waterfall Readiness" multiline text field on the form. The
three summary buckets feed the three coloured callouts at the top of
the form ("Start Blockers" / "Manager Review" / "Efficiency Prompts").

`action_recompute_readiness_lines` writes one
`southbrook.project.readiness.line` row per check, with `status`
(ready/review/blocked/info), `severity` (info/warning/blocker),
`reason`, `evidence` (multiline context — the actual MO names, CAD
status string, work-center load, etc.), and `recommended_action`
(verbatim "do X next" text). The list view of these lines is what
the *Readiness* smart button opens. The rows are blown away and
recreated on every recompute (idempotent — no historical trail of
past readiness, by design — if you need historical, audit the chatter
on the task).

The cron tick:

```python
domain = [
    ("x_southbrook_sale_order_id", "!=", False),
    ("state", "not in", ("1_done", "1_canceled")),
]
tasks = self.search(domain)
for task in tasks:
    previous = task._readiness_snapshot()  # (decision, release_state)
    task._invoke_readiness_recompute()     # tries 3 method names via getattr
    task.readiness_last_recomputed_at = now
    current = task._readiness_snapshot()
    if previous != current and any(previous) and any(current):
        task._log_readiness_flip(previous, current)  # chatter
```

The defensive `getattr` dispatcher means if `southbrook_project_mrp`
renames `action_recompute_readiness_lines`, the cron will silently
fall through to `action_recompute_readiness` or `_recompute_readiness`
without crashing — useful for in-place upgrades on a live instance.

## Quiz (5 questions, applied)

**1.** A task shows decision = REVIEW, score = 90. You scan the
waterfall and see all gates are READY except "Production Capacity:
REVIEW — workcenter load over daily capacity." Why is the score so
high?

> Production Capacity is a REVIEW (warning) gate, not a BLOCKED gate.
> Warnings cost 10 points each; one warning gives a base score of
> 90. None of the capping conditions apply (no missing
> production_count, no CAD open, no material risk, etc.) so the
> linear math wins and the score is 90. The decision is REVIEW
> because *any* warning rolls up to REVIEW, but the planner can
> safely treat this as "low-priority watch list" — score gates are
> tuned so 90+ with a single warning is the "you'll probably be
> fine" zone.

**2.** The cron is running every 30 minutes but a particular task
hasn't had its `readiness_last_recomputed_at` updated in 4 hours.
What's most likely?

> The task fell out of the cron's `domain` filter. Check:
> (a) Is `x_southbrook_sale_order_id` still set? Someone might have
> blanked the link. (b) Has the task's `state` flipped to `1_done`
> or `1_canceled`? The cron skips closed tasks. Either case is
> probably correct behavior — re-link or leave done.

**3.** The "Cabinet Specs" gate is REVIEW and the recommended action
says "missing Material/species, Door style, Finish". You set
`x_southbrook_material_species`, `southbrook_door_style`,
`southbrook_finish` but the gate stays REVIEW. What's wrong?

> The required-specs constant includes a fourth field:
> `x_southbrook_hardware_specs` (Text). The recommended action lists
> what's *currently* missing; if you fixed three out of four, the
> fourth still blocks. Open the Cabinetry Specs tab and paste in
> the hardware spec text from the quote.

**4.** You flip `southbrook_release_bom_verified` to True to
unblock release. The Production Release Checklist gate stays
BLOCKED. Why?

> The release checklist has 12 sub-checks (see lesson 14.4); BoM
> verified is only one. The compute
> `_compute_southbrook_production_release` rebuilds the missing-items
> list on every read and returns BLOCKED if *any* item is missing.
> Open the form and look at the per-item evidence string
> (`_southbrook_production_release_evidence`) to see which item is
> still red. Common culprits: `southbrook_site_measurement_status`
> still pending, no install due date on linked MOs, an unscheduled
> WO.

**5.** A task has `readiness_decision = ready` but `job_at_risk =
True`. Is that a contradiction? What does it mean operationally?

> Not a contradiction — but the Production Capacity gate should have
> fired REVIEW, which should have pushed `readiness_decision` to
> "review". If you're seeing `ready` and `job_at_risk = True`
> together, either the compute hasn't refired since `job_at_risk`
> flipped (open the form to trigger re-evaluate) or the field-deps
> on `_compute_manufacturing_readiness` aren't catching the change
> (file a bug — the dep list does include `job_at_risk`).
> Operationally: trust `job_at_risk` for "is this job late?" and
> trust `readiness_decision` for "should I release more work to
> this?". They're different questions.

---

## What this lesson does NOT cover

- The 5 release sign-off booleans + the Production Release Checklist
  internals → lesson 14.4.
- How a `project.task` becomes linked to MOs (the SO confirm flow) →
  lesson 14.5.
- The custom task views (kanban, calendar, Gantt) that show readiness
  badges → lesson 14.6.
- Project-level rollups (`southbrook_ready_job_count`, etc.) and
  reporting → lesson 14.7.
- The Hermes Console + Fabio recommendation flow that consumes
  readiness as input → Course 3 + Course 7.
- The Manufacturing Intelligence checks (`southbrook.mi.check`) that
  the Calculations gate counts → Course 3 lesson 3.2.
