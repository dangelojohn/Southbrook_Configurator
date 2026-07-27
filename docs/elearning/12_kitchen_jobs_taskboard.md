---
course: 12 — Kitchen Ops Deep Dive
chapter: 12.3
title: Kitchen Jobs / Task Board — The Readiness Engine
duration: 35 minutes
audience: Project Manager + Production Planner (the two who live on this board)
prereqs: Course 2 lesson 2.1 (Kitchen Projects vs Sale Orders). This lesson goes one layer deeper into the `project.task` extensions.
custom_modules: southbrook_premium_orchestration, southbrook_project_mrp, southbrook_kitchen_workspace
---

# Kitchen Jobs / Task Board — The Readiness Engine

## Who this lesson is for

You're the PM or planner who lives on the Kitchen Jobs board all day.
Course 2 lesson 2.1 introduced the three-record (project / order /
task) model. This lesson goes inside the **task** — what makes a task
"ready", how the readiness score is computed, what the swimlanes
mean, what the filters do, and how the cron stitches it together.

If you've ever stared at a card showing `readiness=review` and
wondered "what specifically is the cron checking?" — this is the
lesson.

## Where this lives on the site

> **Kitchen Ops → Kitchen Jobs**

This is the default landing for PMs. The board defaults to the
**Open** filter (excludes `done` / `cancelled` stages) and groups
cards by `readiness_decision`.

> **Kitchen Ops → Kitchen Jobs → List**

Same data, list view — useful when you want to bulk-sort by
`install_due_date` or export to CSV.

> **Kitchen Ops → Kitchen Jobs → \<click a card\>**

The per-task form view. This is where every field on the card has a
deeper story.

## What your screen shows

Each card on the Kitchen Jobs kanban is one `project.task` record.
The fields surfaced on the card (defined in
`southbrook_premium_orchestration/views/kitchen_jobs_views.xml`):

- **Name** (`name` on `project.task`) — composed by the orchestration
  layer as `Kitchen Cabinet Set - <style> (<species>) [<order ref>]`
  from the order line names at sale.order confirmation time.
- **Customer** (`partner_id`) — same partner as on the sale order.
- **Linked SO** (`x_southbrook_sale_order_id`) — the reverse-side
  many2one from task to sale.order. **This is the bidirectional link
  that works on every database, fresh or live.** The forward link
  `sale.order.x_southbrook_project_task_id` exists only on
  UI-extended live DBs.
- **Install due date** (`install_due_date`) — computed from the
  underlying MOs' `x_sbk_install_due_date`, falling back to
  `sale.order.commitment_date` at confirmation time. Editable on the
  task once written.
- **Readiness decision** (`readiness_decision`) — Selection
  (`ready` / `review` / `blocked` / `info`). Computed by
  `_compute_phase1_operational_context`. Drives the kanban grouping.
- **Readiness score** (`readiness_score`) — Integer 0-100. Computed
  from sub-signals. Useful for sorting "most ready first" within a
  swimlane.
- **Production release state** (`southbrook_production_release_state`)
  — Selection (`ready` / `review` / `blocked` / `info`). Distinct
  from readiness; controlled by the five engineer booleans + readiness
  (see lesson 12.4).
- **At risk** (`job_at_risk`) — boolean badge, red. Set by
  `_compute_mrp_status` when the job is behind or blocked relative to
  its deadline.

The kanban has a **progress bar header** for each readiness column
that colour-codes `ready=success` / `review=warning` /
`blocked=danger`. Clicking the band filters the column.

## The readiness sub-signals

A task's `readiness_decision` is computed from
`action_recompute_readiness_lines` in `southbrook_project_mrp`. The
method walks the linked MOs (`production_ids` on the task) and
produces `southbrook.project.readiness.line` records — one per check
type. The standard sub-signals (from
`southbrook_project_mrp/models/project_readiness_line.py`):

| Sub-signal | What it checks | Owning model field |
|---|---|---|
| `cad` | At least one MO has a populated CAD link or `x_cad_status = done` | `mrp.production.x_cad_status` |
| `cutlist` | The production package has a non-empty `sb.cutlist` with substrate set | `sb.cutlist.line_ids` count + substrate |
| `bom` | Every MO has a populated `bom_id` and the BoM has at least one component | `mrp.production.bom_id` |
| `crew` | The task has a `user_ids` assignee whose `hr.employee` has the required skills | `project.task.user_ids` + `x_sbk_required_skill_ids` |
| `equipment` | All routing workcenters have `southbrook_pm_equipment_alerts = 0` | `mrp.workcenter.southbrook_pm_equipment_alerts` |
| `install_date` | `install_due_date` is set and in the future | `project.task.install_due_date` |
| `cabinet_specs` | The task has `x_door_style` + `x_wood_species` + `x_finish` populated (Phase-1 heuristics inferred at confirmation) | `southbrook_specs_complete` computed |

Each sub-signal returns a score 0-100. The `readiness_decision`
banding:

- `ready` — score ≥ 80 AND no blocker-severity sub-signals.
- `review` — score 60-79 OR at least one warning-severity sub-signal.
- `blocked` — score < 60 OR at least one blocker-severity sub-signal.
- `info` — no MOs linked yet (the task exists but the spine isn't
  fully wired).

## The cabinet-spec heuristic fields

When the sale.order's `action_confirm` override creates the spine,
it tries to infer cabinet specs from the order line names. The
heuristics are scoped Phase-1 — they're not authoritative, just a
starting guess for the planner to confirm or correct:

- **Door style** (`southbrook_door_style`) — guessed from the line
  product name's `slab` / `shaker` / `flat panel` / `five-piece`
  tokens. Used by the configurator at re-pricing time.
- **Wood species** (`x_southbrook_material_species`) — guessed from
  `oak` / `maple` / `walnut` / `cherry` tokens.
- **Finish** (`southbrook_finish`) — guessed from `natural` /
  `painted` / `stain` tokens.
- **Hardware specs** (`x_southbrook_hardware_specs`) — left blank;
  filled by the designer or PM during planning.

The DQ cron (Course 2 lesson 2.4 cron 5) reads these — a low
`cabinet_specs` score is what flips a card from green to amber
overnight when a designer forgets to fill them in.

## The board filters

The default search view (`view_kitchen_jobs_search` in
`kitchen_jobs_views.xml`) carries these named filters:

- **Open** — `[('stage_id.fold','=',False)]`. Default on. Hides
  done / cancelled stages.
- **My Jobs** — `[('user_ids','in',uid)]`. Cards where YOU are an
  assignee.
- **Blocked** — `[('readiness_decision','=','blocked')]`. Anything
  the cron decided was missing data.
- **Needs Review** — `[('readiness_decision','=','review')]`.
- **Ready** — `[('readiness_decision','=','ready')]`. Your planning
  pool.
- **At Risk** — `[('job_at_risk','=',True)]`. The PM's escalation
  queue.
- **Missing Install Date** — `[('install_date_missing','=',True)]`.
  Data-quality filter — these are the cards where the spine landed
  but the install date is missing.

Group-by options: readiness, release state, customer.

## Your daily flow

### The PM / planner (start of day, 15 min)

1. Open **Kitchen Ops → Kitchen Jobs**. Default filter Open + group
   by Readiness.
2. **Scan the Blocked column first.** Sort within it by
   `install_due_date` ascending. Open each card whose install is
   within 14 days — the cron flipped these overnight, and the
   chatter has the readiness-line breakdown. Read it; identify the
   failing sub-signal.
3. **For each Blocked card**: chase the artifact owner.
   - Sub-signal `cad` failing → designer / PLM engineer.
   - Sub-signal `cutlist` failing → planner runs `generate_from_mo`
     on the production package (lesson 12.7).
   - Sub-signal `bom` failing → BoM author (typically engineering).
   - Sub-signal `crew` failing → HR / scheduler.
   - Sub-signal `equipment` failing → maintenance.
   - Sub-signal `cabinet_specs` failing → designer.
4. **Move to the Review column.** These are amber. Sort by
   `readiness_score desc` (most-ready first). For each, check the
   sub-signals to see what's keeping it under 80.
5. **Ready column** is your planning pool. Cards here can be
   released to production (if the engineer has signed off the gate —
   lesson 12.4).

### Mid-day check (3 min)

The readiness cron fires every 30 minutes. Refresh the board around
11:00, 14:00, 16:00 — cards may have flipped Ready→Review if an
upstream artifact was invalidated (BoM updated, ECO raised). Cards
RARELY flip Review→Ready mid-day unless someone fixed the artifact
manually.

### End of day (5 min)

- Filter **My Jobs + At Risk**. Add a chatter note on each
  explaining what's blocking and your action plan for tomorrow.
- Confirm **MI Engine Status** shows `last_run_at` within the last
  hour — if the MI refire cron stalled, the gate-state flips you're
  seeing on this board are stale.

## When the readiness cron flips a card overnight

The chatter line you see in the morning reads something like:

> Decision: ready -> blocked, Release state: ready -> blocked.

This is the readiness cron (cron 1 in lesson 2.4,
`_cron_recompute_readiness_all`) detecting that ONE of the
sub-signals changed since the last tick. The cron:

1. Snapshot pre-state: `(readiness_decision, southbrook_production_release_state)`.
2. Calls `action_recompute_readiness_lines`.
3. Stamps `readiness_last_recomputed_at = now()`.
4. Compares post-state to pre-state.
5. If either field changed, posts the chatter note showing both
   transitions.

It doesn't tell you which sub-signal changed. To find that out, open
the task and look at the readiness-lines breakdown
(`readiness_line_ids`) — the line whose `value` is False where it
was True yesterday is the cause.

## Common mistakes + how to recover

**"A card shows readiness=blocked but the score is 95."**

That's a sub-signal carrying blocker severity that doesn't
contribute much to the score. Most common: the `cad` sub-signal is
blocker-severity (no CAD = can't go to production), but on a 7-MO
spine where 6 are CAD-done, the score is high. The decision honours
the blocker regardless. Open the readiness lines; the False blocker
is your target.

**"The card name says 'Kitchen Cabinet Set - White Slab (Maple)
[SO-12455]' but the customer ordered walnut."**

The name was inferred at confirmation time from the FIRST sale
order line. If the order has multiple lines and the first one is
the dummy "setup fee" or "delivery", the inference goes wrong.
Recovery: edit `name` directly on the task; it's free text. Don't
worry about resyncing with the sale order — the field drifts by
design.

**"My MOs are linked to the task via production_ids but the readiness
sub-signal for `bom` is still failing."**

The sub-signal checks `mrp.production.bom_id IS NOT NULL` AND the
BoM has components. If the MO was created via Send-to-Production
with a phantom BoM template, the `bom_id` is set but the
`bom_line_ids` is empty. Open the BoM, add components, save. The
sub-signal flips on the next cron tick (30 min) or you can trigger
a manual recompute via the task's action button.

**"I see `install_due_date` is blank on a card but the sale order
has commitment_date set."**

The copy happens at `action_confirm` time. If the spine task
already existed (from a prior partial run) and confirmation didn't
re-overwrite it, the field stays blank. Recovery: open the order,
run **Backfill Kitchen Task** server action — the idempotent
backfill re-reads the commitment_date.

**"A card is `info` decision with score 0 and no chatter notes."**

`info` is the "no MOs linked yet" state — the spine task exists
but the orchestration hasn't (or can't) link any MOs. Either the
sale order has only non-manufactured lines (services, delivery
fees) or the MO creation step failed silently. Open the order's
chatter for any "failed to create MO" warnings; check the
products are manufactured-type.

**"The board is empty even though I know there are 20 active
projects."**

The action's domain is `[('x_southbrook_sale_order_id','!=',False)]`
— so the board hides tasks without a sale-order link. If your
projects are still in design (`sb.kitchen.project.state =
designing`), no sale order exists yet and no task is on the board.
Look at Sales → Kitchen Workspace → Projects instead for the
design pipeline.

## What the system is doing behind the scenes

The `project.task` model is extended in
`southbrook_project_mrp/models/project_task.py`. The Phase-1
computes (`_compute_phase1_job_context`,
`_compute_phase1_operational_context`) live there. They walk the
task's `production_ids` (the One2many to `mrp.production` added by
the same addon) and roll up readiness, risk, top blocker, and
manufacturing-reality summary.

The readiness recompute (`action_recompute_readiness_lines`) is also
in `southbrook_project_mrp`. It uses the
`southbrook.project.readiness.line` model to record per-sub-signal
state. Each line carries `(task_id, signal_key, value, severity,
score, reason)` — the line records ARE the audit trail.

The compute on the task is **non-stored** but `@api.depends_context("uid")` —
which means it re-evaluates on every page-load for the requesting
user. This makes the kanban responsive without polluting the DB with
denormalised state. The downside: the cron's job is to write the
`readiness_last_recomputed_at` field SO the chatter flip detection
works. Without the cron, you'd never see the chatter "decision
changed" line, even though the live view would show the new state.

The cron's chatter post code (in
`southbrook_premium_orchestration/models/project_task.py`):

```python
if pre_decision != task.readiness_decision \
   or pre_release != task.southbrook_production_release_state:
    task.message_post(body=f"Decision: {pre_decision} -> "
                           f"{task.readiness_decision}, "
                           f"Release state: {pre_release} -> "
                           f"{task.southbrook_production_release_state}.")
```

This is the line you see on chatter every morning. It's the only
audit trail of the overnight flip; the per-sub-signal change has to
be inferred by re-reading the readiness lines.

The `job_at_risk` compute is conservative: it fires when components
are waiting on a started MO, OR an MO is past its deadline, OR the
install date is within 7 days and readiness is still review/blocked.
The search method (`_search_job_at_risk`) lets the kanban filter
use it efficiently without storing.

## Quiz (5 questions, applied)

**1.** You open a card on Kitchen Jobs and see `readiness_decision =
blocked, readiness_score = 92`. The chatter says "Decision: ready ->
blocked." Walk through the diagnosis.

> A blocker-severity sub-signal flipped to False since the last
> cron run. The score is high because most sub-signals are still
> True; the blocker one is dragging the decision regardless. Open
> the readiness lines on the task (`readiness_line_ids`). Find the
> line where `value = False` AND `severity = 'blocker'`. That's
> your cause. Common: `cad` failing because an ECO was opened
> overnight that invalidates the CAD package.

**2.** A PM asks "why does this card say install_due_date = Jan 15
but the sale order's commitment_date is Jan 22?" Walk through the
answer.

> The install_due_date on the task is editable after confirmation,
> and the planner intentionally drifts it from the order's
> commitment_date to build internal slack. The order's date is the
> CUSTOMER-FACING contract date; the task's date is the SHOP-FACING
> internal deadline. Lesson 2.1 covers this. If you want them
> resynced, open the task and re-set the date to match the order's
> commitment_date manually — there's no auto-sync.

**3.** You're looking at a card with `readiness_decision = info,
production_ids = []`. The customer paid 3 days ago. What happened?

> The spine task was created at confirmation time but no MOs were
> created. Most likely the order lines are all non-manufactured
> (delivery, services) OR the MO creation step in
> `_create_kitchen_project_task` errored and was silently logged.
> Open the order's chatter; look for "failed to create MO" or
> "no manufactured products". Recovery: confirm the order lines
> have manufactured products with BoMs, then re-run **Backfill
> Kitchen Task** to retry the MO creation.

**4.** A planner says "the cron should have fired at 03:30 but the
readiness_last_recomputed_at on my tasks is still 22:00 yesterday."
Where do you look first?

> The cron worker is the suspect, not the cron record. Open
> Settings → Technical → Scheduled Actions → Southbrook: Recompute
> Project Readiness. Check `nextcall` — if it's in the past, the
> previous tick crashed. Check `active = True`. Click **Run
> Manually** to fire it synchronously; if it works, the cron is
> probably stuck behind a queue. Restart the Odoo container as a
> last resort — `nextcall` is preserved so the cron picks up after
> restart.

**5.** A new planner asks "I see Cabinet Specs Complete on the form
but it's read-only. How do I edit it?"

> You don't — it's a computed field
> (`southbrook_specs_complete`) reading `southbrook_door_style`,
> `x_southbrook_material_species`, `southbrook_finish`, and
> `x_southbrook_hardware_specs`. Set those four to non-empty values
> and the computed bool flips True automatically. The compute lives
> on the task form's Spec tab. If you've set all four and the bool
> is still False, one of them has whitespace-only content (which
> the compute treats as empty); strip whitespace and re-save.

---

## What this lesson does NOT cover

- The pre-sale `sb.kitchen.project` and its state machine →
  lesson 12.2.
- The five engineer release booleans and the Production Release
  Queue → lesson 12.4.
- The workcenter side of equipment and bottleneck data →
  lesson 12.5.
- MI Engine Status from the planner / sysadmin lens →
  lesson 12.6.
- The cron mechanics (schedule, model, method, last-run reading)
  → Course 2 lesson 2.4.
- The orchestration's `action_confirm` override that creates the
  spine → Course 2 lesson 2.1 "behind the scenes".
- Native Odoo `project.task` mechanics, stages, kanban customisation
  → Odoo's own training.
