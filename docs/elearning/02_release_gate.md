---
course: 2 — Production Planning
chapter: 2.2
title: The Approved -> In Production Release Gate (ENG01)
duration: 30 minutes
audience: Production Planner + ENG01 Production Engineer (the two-person handoff)
prereqs: Lesson 2.1 (Kitchen Projects vs Sale Orders).
custom_modules: southbrook_project_mrp, southbrook_premium_orchestration, southbrook_mrp_kitchen_workcenters
---

# The Approved -> In Production Release Gate (ENG01)

## Who this lesson is for

You're the planner staring at a Kitchen Jobs card that's `readiness=ready`
but `release=blocked`, and you need to get it through the gate. OR you're
the ENG01 production engineer who runs that gate — the human at the
Design Review / Production Engineering workcenter (`code = ENG01`) who
signs off CAD, BoM, cut list, and production notes before a job leaves
your bay. Both of you need to read this. The gate has two sides.

The ENG01 workcenter exists for exactly this purpose; it carries
`x_sbk_station_type = engineering` and a planning-notes string that
reads "Owns the gate between sb.kitchen.project state 'approved' and
'in_production'" — that's not aspirational, that's the contract.

## Where this lives on the site

For the **planner**:

> **Kitchen Ops -> Production Release Queue**

Default-filtered to `review + blocked` release states with at least one
linked sale.order. The queue is whatever isn't `ready` — every card
here is a job waiting on the gate.

For the **engineer**:

> **Kitchen Ops -> Kitchen Jobs**, then click into one card

Or from the per-task form, the **Production Release** tab. That's where
the five gate booleans live and where you tick them off.

The underlying workcenter:

> **Manufacturing -> Configuration -> Work Centers -> Design Review /
> Production Engineering (ENG01)**

Engineers don't usually open this directly, but the planner does when
the engineer is out and the planning notes need a temporary override.

## What your screen shows

On the **Production Release Queue** list:

- **Name** (`name` on `project.task`) — the kitchen job name.
- **Customer** (`partner_id`).
- **Release state** (`southbrook_production_release_state`) — `ready`,
  `review`, `blocked`, or `info`. Rendered as a coloured badge: red
  for blocked, amber for review, green for ready. The queue is
  domain-filtered to `review + blocked` so green never appears here.
- **Readiness score** (`readiness_score`) — 0-100 from the readiness
  cron. Useful for spotting jobs that have great data but a missing
  signature vs jobs that are blocked because the data is incomplete.
- **Install due date** (`install_due_date`) — sort ascending, work
  the tightest deadlines first.
- **Linked SO** (`x_southbrook_sale_order_id`) — click through to the
  order.
- **At risk** (`job_at_risk`) — boolean toggle, surfaces jobs that
  the risk-compute decided won't make their date.

Open one card. The **Production Release** tab on the task form shows
the five sign-off booleans the engineer (or, in their absence, the
planner with a documented note) flips:

- **CAD Approved** (`southbrook_release_cad_approved`) — the CAD model
  exists in `southbrook_freecad_bridge`, has been rendered, and the
  rendering matches what the customer agreed to. Tracking on, chatter
  records who flipped it.
- **Cutlist Approved** (`southbrook_release_cutlist_approved`) — the
  `sb.cutlist` has been generated for every MO in the spine, the panel
  counts and dimensions sanity-check, and the substrate column is set
  (no `false` rows). The MI engine's per-MO cut summary should show a
  yield_pct above 45% and zero `oversized panel` blocker checks.
- **BoM Verified** (`southbrook_release_bom_verified`) — every linked
  `mrp.production` has a populated BoM, hardware lines roll up cleanly
  into `sb.hardware.package`, no `has_pricing_pending` flags are set.
- **Crew Assigned / Reserved** (`southbrook_release_crew_reserved`) —
  the workcenter assignments respect operator skills
  (`hr.skill` matched via `x_sbk_required_skill_ids` on the
  workcenter) and there's a body at every required station for the
  scheduled day.
- **Critical Equipment Available** (`southbrook_release_equipment_available`)
  — the maintenance.equipment records at the routing's workcenters
  are not in `southbrook_condition` `critical` or `offline`. The
  workcenter's `southbrook_pm_equipment_alerts` count tells you the
  number of yellow/red machines at each station.

Below the booleans, two read-only fields:

- **Production Release** (`southbrook_production_release_state`) —
  computed from the five booleans + upstream readiness signals. ALL
  five booleans must be True AND readiness must be `ready` for this
  to compute to `ready`. Anything else is `review` or `blocked`.
- **Production Release Reason** (`southbrook_production_release_reason`)
  — short text explaining which gate failed (e.g. "Cutlist not
  approved" or "Critical equipment offline at CNC01").

## Your daily flow

This lesson splits into two flows — one for the engineer, one for the
planner. They meet in the middle on each release decision.

### The engineer's flow (ENG01)

**Per release decision (typically 6-12 per day).**

A card lands in your queue at `release=review` — the upstream
artifacts exist but no one's signed off yet.

1. Click into the task. Look at the **Production Release** tab.
2. **CAD check.** Open the linked freecad render (if the bridge is
   active) or the configurator's spec sheet PDF. Compare to the design
   the customer approved on `sb.kitchen.project.selected_design_option_id`.
   If it matches, flip **CAD Approved**.
3. **Cutlist check.** Open the **Manufacturing -> Manufacturing Orders**
   linked from the task. For each MO, look at its production package
   (`sb.production.package`), open the cutlist, scan the line count and
   the substrate column. Also check the MI engine's per-MO blockers
   (`x_mi_blocker_count`) — anything > 0 means stop and read the
   `x_mi_check_ids` list. Common blockers: `Oversized panel` (panel
   exceeds the workcenter's `x_sbk_max_panel_length_mm`), `Missing
   cutlist`. If clear, flip **Cutlist Approved**.
4. **BoM check.** On the same MO form, the BoM tab. Confirm hardware
   rolls up (the `sb.hardware.package` should be in `picked` or
   `delivered` state, not `draft`). Look at `has_pricing_pending` on
   the package — if True, the MI engine has already filed a
   `Hardware pricing pending` warning; investigate before flipping
   BoM Verified.
5. **Crew check.** Open the Manufacturing schedule for the planned
   release day. Confirm an operator is on the calendar for each
   bottleneck workcenter (`x_sbk_is_bottleneck = True`) the MO
   touches. Flip **Crew Assigned**.
6. **Equipment check.** On each routing workcenter, look at
   `southbrook_pm_equipment_alerts`. Zero is green-light. If any
   machine at a workcenter is in `critical` or `offline`, escalate
   to maintenance BEFORE flipping the boolean — flipping it green
   when a key machine is down is the most common source of
   bad-release incidents.
7. With all five booleans True, the computed
   `southbrook_production_release_state` flips to `ready`. The card
   disappears from the Production Release Queue and lights up green
   on the planner's Kitchen Jobs board. **Your sign-off is now
   on chatter** — anyone investigating later can see which engineer
   approved and when.

### The planner's flow

**Per release decision (parallel to the engineer's flow).**

1. Open **Kitchen Ops -> Production Release Queue** at start of
   day. Sort by `install_due_date` ascending.
2. For each card, eyeball `readiness_score` and the
   `southbrook_production_release_reason` text. The reason names the
   specific failed gate.
3. **If readiness < 60 and the reason is data-completeness:** don't
   bother the engineer. The card isn't ready for the gate yet; fix
   the upstream data first (chase the designer for `x_door_style` /
   `x_wood_species` / `x_finish`, ask the BoM owner to populate, etc).
4. **If readiness >= 70 and the gate is `review`:** ping the engineer
   to actually look at it. Add a chatter note with the install date
   so they can prioritise.
5. **If readiness >= 70 and the gate is `blocked` because of a
   `southbrook_release_equipment_available = False`:** open the
   workcenter (`mrp.workcenter`) at the failing station, look at the
   maintenance.equipment list, and see if the planner can route the
   work to an alternative (`alternative_workcenter_ids`). If yes,
   the engineer just flips the equipment boolean after re-routing.
   If no — escalate to maintenance.
6. When the engineer signs off, the card moves to `release=ready`
   and disappears from this queue. Now it goes into your normal
   schedule (lesson 2.3).

## Emergency bypass (planner-side only, audit-tracked)

Once per quarter or so something genuinely cannot wait. The customer's
contractor is on site, the cabinets need to ship tomorrow, and ENG01
is at lunch. The system does not have a "force release" button —
flipping the boolean fields is the bypass. **What you do:**

1. Open the task, **Production Release** tab.
2. Flip the booleans that are actually approved (don't lie — flip
   only the ones whose underlying artifact really is OK).
3. For the one you're bypassing, flip it True ANYWAY but post a
   chatter note on the task explaining what's being bypassed, the
   business reason, and who approved (PM name + verbal phone
   acknowledgement).
4. Open the workcenter (`mrp.workcenter` ENG01) and add a note in
   `x_sbk_planning_notes` so the engineer sees the bypass on Monday
   morning. They will either ratify it or back it out — that's their
   call, not yours.
5. The chatter note is the audit trail. Without it, the MI engine's
   `_cron_refire_gates` will re-evaluate the gate overnight and may
   flip the state back to `blocked`, which surfaces the bypass to
   the production manager via the MI Engine Status board.

## Common mistakes + how to recover

**"I ticked CAD Approved and the release state stayed at `blocked`."**

The release state is a compute, not a write. All five booleans must
be True AND the upstream `readiness_decision` must be `ready`. If
readiness is still `blocked`, your engineer-side boolean doesn't
move the state. Check the readiness score and reason; that's where
the actual block lives.

**"The engineer ticked all five booleans but the card is still in
the queue."**

The queue is domain-filtered to `release_state in ('review',
'blocked')`. After the booleans are all True, the compute runs on
the next save (or on the next readiness cron tick, every 30 min).
Refresh the queue. If it's still there after 30 minutes, the
readiness compute is the holdup — open the card, look at the
readiness lines breakdown.

**"I flipped Cutlist Approved but the cutlist itself shows zero
lines."**

You approved an empty cutlist. The system doesn't prevent this — the
boolean is your judgement, not a generated guarantee. Recovery:
flip it back to False, open the production package, run
`generate_from_mo()` (the action button on the package form), and
re-evaluate.

**"Crew check passed but on the day of release nobody showed up at
SB-CNC-BORE because the assigned operator called in sick."**

That's a real-world failure, not a system failure. Recovery path:
the workcenter has `alternative_workcenter_ids` (CNC02 is the
configured backup for CNC-BORE). The planner re-routes the day's
MOs to CNC02 — see lesson 2.3 for the bottleneck-rerouting flow.
The release stays valid; only the schedule needs to change.

**"The release state flipped from `ready` back to `blocked`
overnight."**

The MI engine's `_cron_refire_gates` ran (hourly cron — see lesson
2.4) and re-evaluated the gate. Something downstream changed: an
ECO was raised against the BoM, a piece of equipment went into
critical condition, a crew assignment was archived. Open the task,
look at the most recent chatter note from the MI engine, follow
the breadcrumb. **Do not just flip the boolean back.** Figure out
what changed and either fix it or re-approve with the new
information.

## What the system is doing behind the scenes

The five sign-off booleans live on `project.task` (added by
`southbrook_project_mrp`). The computed
`southbrook_production_release_state` reads them PLUS the upstream
`readiness_decision` and emits one of `ready` / `review` / `blocked`
/ `info`. The compute is registered on the task and runs on every
save of the relevant booleans, and on every readiness cron tick.

The Production Release Queue (`action_production_release_queue` in
`southbrook_premium_orchestration/views/production_release_views.xml`)
is just a list view on `project.task` with the domain
`[('southbrook_production_release_state','in',('review','blocked')),
('x_southbrook_sale_order_id','!=',False)]`. That domain is why a job
without a sale-order link never shows up here — internal admin tasks
don't count.

Every flip you make on the booleans is tracked on chatter (the fields
carry `tracking=True`). The MI engine's hourly `_cron_refire_gates`
re-evaluates every active gate check (`southbrook.mi.check` records
with `is_gate=True`) against every in-flight MO. That cron is the
reason a release can revert overnight — it catches data changes that
invalidate a prior approval. The cron's last run details show up on
**Kitchen Ops -> MI Engine Status** so you can confirm it ran clean.

The ENG01 workcenter itself (`code = ENG01`,
`x_sbk_station_type = engineering`, `x_sbk_is_bottleneck = False`,
`x_sbk_allows_parallel_jobs = True`) is seeded by
`southbrook_mrp_kitchen_workcenters/data/mrp_workcenter_seed.xml`. It
exists in the workcenter list so the routing for the engineering
operation step can point at it; the engineer-as-a-workcenter framing
also lets the planning baseline cron see "engineering capacity" the
same way it sees CNC capacity.

## Quiz (5 questions, applied)

**1.** The engineer says "I just flipped all five booleans on the
12455 task but it's still showing `blocked` on your queue." What's
the most likely cause and how do you check?

> The upstream `readiness_decision` is still `blocked`. The release
> state is the AND of all five engineer booleans AND the readiness
> decision being `ready`. Open the task, look at `readiness_score`
> and the readiness lines breakdown. If a BoM line is missing or
> drawings are missing, that's the actual block; the five booleans
> are necessary but not sufficient.

**2.** A customer is screaming at the PM because their install is
tomorrow and the job is `release=blocked`. The block is on
`southbrook_release_equipment_available = False` because the HOMAG
edge bander (SB-EDGE) is in `critical` condition. You can't fix
the machine in time. What's the realistic recovery?

> Reroute the MO around SB-EDGE for tonight's run. SB-EDGE doesn't
> have a configured alternative in the seed data (it's marked as a
> bottleneck precisely because it's irreplaceable), so this means
> shipping unbanded panels and committing to band them on-site
> with a portable bander, OR pushing the customer's install by 24
> hours. Both decisions are above your pay grade — escalate to the
> PM. If they decide ship-unbanded, **document the bypass** in
> chatter on the task AND on the workcenter's
> `x_sbk_planning_notes`.

**3.** You're the engineer at ENG01 and you're looking at a cutlist
with 47 lines, one of which is a `Side L` panel that's 2900mm long.
The MI check tab shows a blocker: "Oversized panel: Side L is 2900
x 600 mm and does not fit a 2440 x 1220 mm sheet." Do you flip
Cutlist Approved?

> No. The blocker is real — the sheet stock physically can't carry
> a 2900mm panel. Recovery: push back to the designer to split the
> panel (two pieces with a centre joint) or to source a non-standard
> 3050x1220 sheet. Don't flip the boolean to silence the warning;
> the floor will discover it at SB-SAW and the rework cost is much
> higher than a 10-minute design conversation now.

**4.** A planner asks "can I flip the engineer's booleans for them
if they're sick?" What's the right answer?

> Technically yes (the fields aren't ACL-locked to the engineer).
> But you OWN the decision once you flip it. The system tracks
> which user wrote the boolean, so the audit trail will show you
> as the approver. Only do it if you'd genuinely sign your name to
> the artifact (e.g. you actually opened the CAD render and
> compared to the customer design). Most planners don't have the
> CAD skills for this; better to escalate to a backup engineer or
> push the release decision to tomorrow.

**5.** The MI engine `_cron_refire_gates` cron is configured to run
every hour. A release was approved at 09:00 and re-evaluated to
`blocked` at 10:00. The task's chatter shows the MI engine flipped
it because `is_gate` checks fired a new blocker. Which check most
likely fired between 09:00 and 10:00?

> An ECO was raised against the BoM or the cutlist between 9 and
> 10. ECOs in `state = open` are the most common cause of a
> mid-day release-state revert because they invalidate the BoM
> Verified boolean's underlying artifact. Check
> `southbrook.eco` records linked to the affected MO; if one is
> open, the engineer needs to either approve the ECO and
> re-verify the BoM or close the ECO if it was raised in error.

---

## What this lesson does NOT cover

- The shape of the Kitchen Jobs board and the difference between
  readiness and release states -> lesson 2.1.
- How to schedule a released job against bottleneck workcenters
  -> lesson 2.3.
- What the 6 nightly crons (readiness, MI refire, analytics
  backfill, planning baseline, DQ, ECO proposal) do -> lesson 2.4.
- How the MI engine's per-MO checks are generated and read -> lesson
  2.5.
- Engineering Change Orders (ECOs) — when to raise one, how state
  transitions work -> Course 4, lesson 4.1.
- Native Odoo MRP workcenter setup, routing definitions, and BoM
  authoring -> Odoo's own training.
