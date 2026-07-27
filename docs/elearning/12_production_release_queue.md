---
course: 12 — Kitchen Ops Deep Dive
chapter: 12.4
title: Production Release Queue — The Five Booleans and the Bypass
duration: 40 minutes
audience: Planner + ENG01 Production Engineer (the two-person handoff)
prereqs: Course 2 lesson 2.2 (Release Gate). This lesson goes deeper into the booleans, the bypass, and rollback.
custom_modules: southbrook_premium_orchestration, southbrook_project_mrp, southbrook_mrp_kitchen_workcenters
---

# Production Release Queue — The Five Booleans and the Bypass

## Who this lesson is for

You're the planner or ENG01 engineer who runs the daily release
gate. Course 2 lesson 2.2 introduced the gate at a working level —
what the booleans mean, who flips each, the per-flow steps. This
lesson goes a layer deeper: the **detailed flip mechanics**
(tracking, search, ACL), the **emergency bypass workflow with the
audit trail**, the **rollback path** when a release goes bad after
the cabinets are already cut, and the **interaction between the
five booleans and the readiness compute** that makes a "valid" flip
sometimes a no-op.

If you've ever flipped all five booleans and watched the state stay
`blocked`, this lesson tells you why.

## Where this lives on the site

For the planner:

> **Kitchen Ops → Production Release Queue**

The list view of `project.task` records, default-filtered to
`southbrook_production_release_state in ('review', 'blocked')` AND
`x_southbrook_sale_order_id != False`. The action is
`action_production_release_queue` in
`southbrook_premium_orchestration/views/production_release_views.xml`.

For the engineer:

> **Kitchen Ops → Kitchen Jobs → \<open a card\>**

The Production Release tab on the task form. That's where the five
booleans live. Same model (`project.task`), same fields, different
framing.

For the ENG01 workcenter (where the engineer "lives"):

> **Manufacturing → Configuration → Work Centers → Design Review /
> Production Engineering (ENG01)**

Code `ENG01`, `x_sbk_station_type = engineering`,
`x_sbk_is_bottleneck = False`, `x_sbk_allows_parallel_jobs = True`.
Seeded by
`southbrook_mrp_kitchen_workcenters/data/mrp_workcenter_seed.xml`.

## What your screen shows

On the Production Release Queue list:

- **Name** (`name` on `project.task`).
- **Customer** (`partner_id`).
- **Release state** (`southbrook_production_release_state`) —
  rendered as a colour-coded badge (red for blocked, amber for
  review, green for ready; though green is filtered out by the
  action domain).
- **Readiness score** (`readiness_score`).
- **Install due date** (`install_due_date`).
- **Linked SO** (`x_southbrook_sale_order_id`).
- **At risk** (`job_at_risk`) — optional column, hidden by default.

On the per-task **Production Release** tab, the five booleans plus
the computed state + reason:

- **CAD Approved** (`southbrook_release_cad_approved`) — Boolean,
  `tracking=True`.
- **Cutlist Approved** (`southbrook_release_cutlist_approved`) —
  Boolean, `tracking=True`.
- **BoM Verified** (`southbrook_release_bom_verified`) — Boolean,
  `tracking=True`.
- **Crew Assigned / Reserved** (`southbrook_release_crew_reserved`) —
  Boolean, `tracking=True`.
- **Critical Equipment Available**
  (`southbrook_release_equipment_available`) — Boolean,
  `tracking=True`.
- **Production Release** (`southbrook_production_release_state`) —
  computed, readonly. Selection: `ready` / `review` / `blocked` /
  `info`.
- **Production Release Reason**
  (`southbrook_production_release_reason`) — computed, readonly.
  Free text explaining the failing item (e.g. "Missing CAD approved,
  Cutlist approved.").

## The full compute — what makes the state `ready`

This is where Course 2 lesson 2.2's simplification matters. The
compute in
`southbrook_project_mrp/models/project_task.py:_compute_southbrook_production_release`
walks `_southbrook_missing_production_release_items()` which checks:

1. `southbrook_site_measurement_status` ∈ `('received', 'waived')`.
2. `southbrook_release_cad_approved` OR `job_cad_status` contains
   "done".
3. `southbrook_release_cutlist_approved`.
4. `southbrook_specs_complete` (computed from door style + species +
   finish + hardware specs being non-empty).
5. `southbrook_release_bom_verified`.
6. `production_count > 0` (Linked MOs).
7. `components_available == "ready"` (every linked MO fully reserved).
8. `workorder_count > 0` AND `unscheduled_workorder_count == 0`.
9. `crew_gap = False` OR `southbrook_release_crew_reserved = True`.
10. `equipment_blocked = False` AND
    `southbrook_release_equipment_available = True`.
11. `job_install_due` is set.

If ALL eleven pass, state = `ready`. Any missing item → state =
`blocked` with reason = "Missing X, Y, Z."

This is broader than just five booleans — there are six DATA
prerequisites (site measurement, specs, MOs, components, WOs,
install date) that the engineer can't override by flipping a
boolean. The five booleans gate the engineer's SUBJECTIVE sign-offs
(CAD looks right, cutlist looks right, BoM looks right, crew is
there, equipment works). The other six gate the OBJECTIVE data
state — the booleans don't replace them.

## Who flips each boolean — the responsibility map

| Boolean | Who flips | Underlying artifact they verified |
|---|---|---|
| `southbrook_release_cad_approved` | ENG01 engineer (preferred) OR designer / PLM engineer (with engineer's verbal ack) | FreeCAD render exists OR `job_cad_status` contains "done"; matches `selected_design_option_id`. |
| `southbrook_release_cutlist_approved` | ENG01 engineer | `sb.cutlist` exists, lines > 0, substrate set; MI engine's per-MO `x_mi_blocker_count = 0`. |
| `southbrook_release_bom_verified` | ENG01 engineer | Every linked MO has `bom_id`; hardware package in `picked` or `delivered` state; `has_pricing_pending = False`. |
| `southbrook_release_crew_reserved` | Planner | Skills match (`x_sbk_required_skill_ids` on workcenter ↔ `hr.skill` on assignees); body at every bottleneck station for the planned day. |
| `southbrook_release_equipment_available` | ENG01 engineer + maintenance lead | Every routing workcenter has `southbrook_pm_equipment_alerts = 0`. |

The fields don't have ACL restrictions — anyone with write access
to `project.task` can flip any boolean. The tracking is the audit
trail: every flip lands on chatter with the user who wrote.

## The emergency bypass workflow

Once per quarter or so, a customer install is tomorrow and the
ENG01 engineer is unreachable. The system has NO "force release"
button — flipping the booleans IS the bypass. Course 2 lesson 2.2
covered the basic steps; here's the full audit-tracked version:

### When bypass is appropriate

- Install date < 48 hours away AND
- All five engineer artifacts are actually OK (you've physically
  looked) AND
- The engineer is unreachable for verbal sign-off AND
- The PM has authorised the bypass in writing (chatter note OR
  email).

### When bypass is NOT appropriate

- The cutlist has an MI engine blocker check (`Oversized panel`,
  `Missing cutlist`) — that's a real data problem, not a sign-off
  delay.
- An equipment alert is `critical` or `offline` — bypassing this
  ships defective product.
- The customer hasn't actually approved the latest design — bypassing
  this ships the wrong cabinets.

### The bypass procedure

1. **Open the task**, Production Release tab.
2. **Verify each artifact**. Open the CAD render, look at it. Open
   the cutlist, scan lines. Open the BoM, check components. Walk the
   floor and check the equipment. **Don't lie** — if you haven't
   actually verified, you're shipping a release without the gate.
3. **Flip the booleans you actually verified.** Each flip lands on
   chatter with your user.
4. **Post a chatter note** ON THE TASK explaining: bypass reason,
   who authorised (PM name + phone-call timestamp), what artifacts
   you personally verified, when the engineer is expected back, and
   any open risk.
5. **Update `x_sbk_planning_notes`** on the ENG01 workcenter with
   a one-liner pointing to the bypassed task: "BYPASSED: task
   <name>, Customer <partner>, ratify Monday." The engineer sees
   this when they next open the workcenter form.
6. **Send an email to the PM** (out-of-band) summarising what you
   did. The chatter is the system audit trail; the email is the
   business audit trail.

### What happens after bypass

The MI gate refire cron (Course 2 lesson 2.4 cron 2,
`_cron_refire_gates`) runs every hour. It re-evaluates every active
gate check against every in-flight MO. If a gate check fires a
blocker for the bypassed task (e.g. the cutlist actually had a
blocker you missed), the gate check writes a check row and the
recommendation engine catches it. The release state may flip back
to `blocked` overnight — that's the system catching the bypass.

The engineer, returning to work, opens the task and sees:
- Five booleans flipped by you.
- Chatter showing your bypass note + each boolean flip.
- Possibly a refire-cron-induced flip back to blocked.

They either ratify (everything was fine, leave booleans True) or
back out (flip the failing one back to False and address the actual
issue). That's their judgement, not yours.

## The rollback when a release goes bad after the floor starts

This is the situation Course 2 didn't cover: the gate passed, the
floor started, and the cabinets are partially cut when something
discovers a problem (wrong species, wrong dimensions, BoM error).

### Step 1 — Stop the floor

1. Open every linked MO from the task (`production_ids`).
2. For each, click **Mark as Done → Cancel** OR put the work orders
   into `paused` state. Don't unlink — you'll lose the audit trail.
3. Post a chatter note explaining the rollback reason.

### Step 2 — Reset the release state

The release state is **computed**, not stored, so you can't "set it
back to review" directly. Flip the relevant booleans BACK to False:

- If the BoM was wrong: `southbrook_release_bom_verified = False`.
- If the cutlist was wrong: `southbrook_release_cutlist_approved =
  False`.
- If the CAD didn't match: `southbrook_release_cad_approved = False`.

The compute re-runs immediately on save; state flips back to
`blocked` and the task lands on the Production Release Queue again.

### Step 3 — Quantify the damage

How many panels were cut? How many already banded? How many
assembled? Open the MOs' work order durations to see. Anything that
was started counts as scrap unless it can be reused (different
cabinet, similar dimensions).

### Step 4 — Fix the upstream artifact

The whole point of rollback is that the upstream artifact (BoM /
cutlist / CAD) was wrong. Open it, fix it, re-verify. The fix
typically requires:

- An ECO (`southbrook.eco`) raised against the BoM to track the
  change.
- A new cutlist via `generate_from_mo` on the production package.
- A new CAD render via the FreeCAD bridge.

### Step 5 — Re-release

After the upstream is fixed and re-verified, re-flip the booleans.
The compute re-fires; state goes back to `ready`. Re-confirm the
MOs (Manufacturing → MO → Reset to Draft → Confirm). The floor
picks up from where they stopped (or from scratch if the scrap was
heavy).

The whole chain MUST land on chatter. Without the trail, the next
audit can't reconstruct what happened.

## The interaction with the readiness compute

A common confusion: **flipping all five booleans is necessary but
not sufficient for `ready`.** The compute also reads the SIX data
prerequisites (site measurement, specs, MOs, components, WOs,
install date). The readiness sub-signals contribute to many of
those:

- `readiness_decision` doesn't directly appear in the release
  compute, but the data sub-signals it reads (BoM, CAD, cutlist)
  also feed the release compute via `job_cad_status`,
  `southbrook_specs_complete`, `production_count`, etc.

So when the engineer says "I flipped all five booleans, why is it
still blocked?":

1. Re-read the `southbrook_production_release_reason` — it names
   the specific missing item.
2. If it says "Missing components available", the issue is
   `components_available != 'ready'` — go to the MOs and reserve
   components.
3. If it says "Missing Schedule work orders", the issue is
   `unscheduled_workorder_count > 0` — schedule the WOs.
4. If it says "Missing Crew assigned/reserved", the issue is the
   `crew_gap` compute returning True AND
   `southbrook_release_crew_reserved = False` — assign a user OR
   flip the boolean.

The reason field is the truth. Read it before chasing artifacts.

## Your daily flow

This is the same as Course 2 lesson 2.2 — read that first for the
basic flow. The additions here:

**Per release decision (engineer):**

- After flipping the five booleans, **REFRESH the task form** before
  declaring the gate clear. The compute fires on save; if you don't
  refresh, you're looking at stale fields.
- If the state stays `blocked` after refresh, read the **reason**.
  The fields you skipped are listed.

**Per bypass (planner):**

- Always post a chatter note BEFORE flipping the bypassed boolean.
  If you forget, the chatter shows "field flipped" without context;
  the audit reconstruction is painful.

**Per rollback (joint):**

- The engineer flips the bad boolean back. The planner cancels the
  MOs. They MUST coordinate; one without the other leaves an
  inconsistent state (booleans say "approved" but MOs are cancelled,
  or MOs running while booleans say "blocked").

## Common mistakes + how to recover

(Course 2 lesson 2.2 covers the basic ones. The new ones here:)

**"I flipped CAD Approved and Cutlist Approved, the reason says
'Missing BoM verified.' I flipped that boolean too but the reason
still says it."**

The compute didn't re-fire. Save the form (the floppy disk icon)
explicitly — the boolean flip is a UI write, but the page-level
save fires the compute. If saving doesn't help, the
`@api.depends` may not include the field you just flipped (unlikely
but possible after a code change); force-recompute via the
task action menu.

**"I bypassed the release Friday night, the engineer ratified
Monday, but Wednesday it flipped back to blocked overnight."**

The MI gate refire cron caught an actual issue that wasn't apparent
Friday or Monday. Check the most recent chatter note from the MI
engine — it names which check fired. Likely candidates: an ECO was
raised against the BoM, an equipment record condition flipped, a
crew assignment was archived. Address the underlying issue; don't
re-flip the boolean to silence the cron.

**"I want to release a job but the reason says 'Missing Linked
MOs.'"**

The spine task exists but no MOs are linked. Open the sale order,
look at the order lines — if they're all services / non-manufactured
products, there's nothing to manufacture and the spine shouldn't be
on the release queue (it shouldn't be in the queue domain either,
but Phase 1 doesn't filter on this). Likely the planner needs to
manually create MOs from the order lines OR the order has the
wrong product type and needs correction. Don't bypass this — it's
data-state, not sign-off.

**"The release state went from `ready` to `info` overnight."**

`info` is the catch-all for "not enough data to decide." Something
on the task was archived or unlinked. Open the task, look at
`production_ids` (any MOs left?), `production_count`, then check
the chatter for what was unlinked. If an MO was deleted (rare but
possible from sysadmin actions), recover by re-running **Backfill
Kitchen Task** on the sale order.

**"I rolled back a bad release, fixed the BoM, re-flipped the
booleans, but the MOs are still cancelled."**

Cancelling an MO is a separate action from flipping the gate
booleans. The booleans control the GATE; the MOs are downstream
artifacts. Re-open each MO and click **Reset to Draft → Confirm**
to put them back to confirmed state. The work orders re-generate
from the routing.

## What the system is doing behind the scenes

The five booleans live on `project.task` (added by
`southbrook_project_mrp`). They have `tracking=True` so every flip
appears in chatter with the user identity. They have no `groups`
restriction — anyone with write access on `project.task` can flip.

The compute `_compute_southbrook_production_release` runs on every
save of any of the dependent fields (the eleven items above). Its
`@api.depends` includes all five booleans plus the data prerequisites.
It calls `_southbrook_missing_production_release_items` to build
the list, then sets state + reason accordingly.

The search method `_search_southbrook_production_release_state`
exists because the compute is non-stored — without it, the Production
Release Queue's domain (`southbrook_production_release_state in
('review', 'blocked')`) wouldn't work. The search builds a domain
on the underlying fields to deliver tasks whose computed state
matches the requested value.

The reason text is recomputed alongside the state. Reading
`southbrook_production_release_reason` is the fastest way to know
"what's missing" without opening the form.

The MI gate refire cron (`_cron_refire_gates` in
`southbrook.mi.engine.state`) re-evaluates every active gate check
hourly. A gate check that fires writes a `southbrook.mi.check` row,
which can flip `x_mi_status` on the production package, which can
flip `southbrook_release_bom_verified` if the BoM check is on
the gate set. This is the chain by which an Monday-ratified
bypass can revert by Wednesday — the gate check is doing its job.

The audit trail is split:
- **Chatter on the task** — every boolean flip, the user, the
  timestamp.
- **Chatter on the workcenter** (`x_sbk_planning_notes` updates) —
  bypass narrative.
- **`ir.logging`** — cron output, including which check fired and
  why.

A complete audit reconstruction reads all three.

## Quiz (5 questions, applied)

**1.** You flip all five booleans on a task with `install_due_date =
tomorrow`, state stays `blocked`, reason says "Missing Schedule work
orders." What does this mean and how do you fix?

> The compute reads `unscheduled_workorder_count` — if any linked
> WO has no `date_planned_start`, the gate stays blocked even though
> the engineer signed off. Open **Manufacturing → Work Orders**,
> filter by the task's MOs, schedule the unscheduled WOs against
> their workcenters. The compute re-fires on save; state flips to
> `ready` once every WO has a planned start. The booleans alone
> don't cover scheduling — that's the planner's job.

**2.** The engineer is sick on a Tuesday with an install tomorrow.
The PM tells you to bypass. Walk through the bypass procedure
end-to-end.

> (1) Verify each artifact yourself: open the CAD render, scan the
> cutlist, walk the BoM, confirm crew on the calendar, check the
> equipment list. (2) If everything is actually OK, flip the five
> booleans on the task. (3) Post a chatter note on the task
> explaining the bypass: PM authorised by phone at <time>, you
> verified each artifact at <time>, engineer expected back <day>.
> (4) Open the ENG01 workcenter (Manufacturing → Workcenters → ENG01),
> add a line in `x_sbk_planning_notes`: "BYPASSED: task <name>,
> ratify <day>." (5) Email the PM a summary so the business has its
> own audit trail. The chatter alone is fine for the system audit
> but the email is the business contract.

**3.** A release was approved Monday, the floor cut 40 panels
Tuesday, then Wednesday the planner discovers the BoM had the wrong
hinge type. Walk through the rollback.

> (1) Stop the floor: cancel or pause the linked MOs.
> (2) Flip `southbrook_release_bom_verified = False` on the task.
> Compute fires, state goes back to `blocked` with reason
> "Missing BoM verified." Task lands on Production Release Queue.
> (3) Quantify damage: 40 panels cut, count how many are reusable
> (different cabinet, same dimensions). Scrap the rest via
> `stock.scrap`. (4) Raise a `southbrook.eco` against the BoM with
> the hinge correction; PLM engineer reviews + approves. (5) Once
> the BoM is fixed, re-flip `southbrook_release_bom_verified = True`.
> Compute fires, state goes back to `ready`. (6) Reset MOs to draft,
> confirm, re-start the floor. Every step lands on chatter; this is
> the audit reconstruction the next quality review will read.

**4.** A planner asks "if the engineer's booleans are necessary but
not sufficient, what's actually sufficient for a `ready` state?"

> The compute checks ELEVEN items: 5 engineer booleans + 6 data
> prerequisites (site measurement, cabinet specs, linked MOs,
> components ready, WOs generated + scheduled, crew + equipment +
> install date). The five booleans gate engineer judgement; the six
> data items gate objective data state. ALL eleven must pass. The
> reason field always names the failing one. Read the reason; don't
> just count booleans.

**5.** The release state flipped from `ready` back to `info`
overnight. The chatter shows no MI engine note. What's the
diagnosis?

> `info` means "not enough data to decide" — typically the linked
> MOs got unlinked (deleted, archived, or the spine lost its
> `production_ids`). Open the task; if `production_count = 0`, the
> spine is empty. Check the sale order's chatter for any
> auto-action that may have cancelled MOs. Recovery: run
> **Backfill Kitchen Task** on the sale order to re-create the
> spine and re-link MOs. The compute re-fires on save; state
> returns to either `blocked` (more data missing) or `review` /
> `ready` if the boolean booleans were preserved.

---

## What this lesson does NOT cover

- The basic gate-flow each role does day-to-day → Course 2 lesson 2.2.
- The Kitchen Jobs board and how readiness flows in →
  lesson 12.3 + Course 2 lesson 2.1.
- Bottleneck-aware scheduling once a job is released →
  Course 2 lesson 2.3 + lesson 12.5.
- The MI gate refire cron mechanics — schedule, last-run, failure
  modes → Course 2 lesson 2.4 cron 2.
- The MI Engine Status board → lesson 12.6.
- ECO authoring details → Course 4 lesson 4.1.
- Native Odoo work-order scheduling and resource calendar mechanics
  → Odoo's own training.
