---
course: 2 — Production Planning
chapter: 2.3
title: Bottleneck-Aware Scheduling — Cutting, Edge Banding, CNC
duration: 30 minutes
audience: Production Planner (the person who sequences MOs against workcenters)
prereqs: Lessons 2.1 and 2.2. Native Odoo MRP workcenter + routing knowledge assumed.
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_pm, southbrook_premium_orchestration
---

# Bottleneck-Aware Scheduling — Cutting, Edge Banding, CNC

## Who this lesson is for

You're the planner who's just had a job land in your "Ready" column on
Kitchen Jobs (lesson 2.1), the ENG01 engineer signed off the gate
(lesson 2.2), and now you have to decide which workcenters this MO
runs through, on which day, in which sequence. Southbrook has eight
bottleneck stations and three of them — Panel Saw, Edge Bander, CNC
Boring — eat your day if you over-schedule them. This is the lesson
where you learn to read the bottleneck flag, route around breakdowns,
and not let a single broken machine cascade into a week of late
installs.

## Where this lives on the site

> **Kitchen Ops -> Workcenter Bottlenecks**

The bottleneck board — all active `mrp.workcenter` records, default
kanban view. Each tile shows load vs capacity; bottleneck-flagged
stations sort to the top.

> **Southbrook PM -> Floor Load**

Same workcenter list, different framing — what the PM uses on their
walk-around. Identical underlying data.

> **Manufacturing -> Configuration -> Work Centers -> <station>**

The per-workcenter form where you edit `alternative_workcenter_ids`,
`x_sbk_is_bottleneck`, and the cycle-time fields.

> **Southbrook PM -> Ready Queue**

The list of confirmed MOs waiting to be scheduled. This is where you
pick from when you sit down to sequence the next 24 hours.

## What your screen shows

On **Workcenter Bottlenecks** (the kanban), each tile shows:

- **Workcenter name + code** (`name`, `code` on `mrp.workcenter`) —
  e.g. "Panel Saw / CNC Nesting (SB-SAW)".
- **In-flight WOs** (`southbrook_pm_inflight_count`) — work orders in
  `pending` / `waiting` / `ready` / `progress`. **The busy-now metric.**
  Live compute, no cron.
- **Done today** (`southbrook_pm_throughput_today`) — work orders that
  finished here since midnight. Coarse throughput.
- **Late MOs** (`southbrook_pm_late_count`) — MOs with a work order at
  this station whose `date_deadline` has passed and which aren't done
  yet. **This is your alarm bell.**
- **Equipment alerts** (`southbrook_pm_equipment_alerts`) — count of
  maintenance.equipment records here whose `southbrook_condition` is
  `fair` / `watch` / `critical` / `offline`. Tap to see which
  machines.
- **Bottleneck badge** — visible when `x_sbk_is_bottleneck = True`.
  These stations are the ones you can't overload without consequence.
- **Station type** (`x_sbk_station_type`) — `cutting`, `cnc`,
  `edge_banding`, `assembly`, `finishing`, etc.
- **Allows parallel jobs** (`x_sbk_allows_parallel_jobs`) — True for
  stations that can run multiple WOs concurrently (Cure Room, Door
  Hanging, Assembly), False for one-at-a-time stations (Panel Saw,
  Edge Bander, CNC Boring, Paint Booth).
- **Alternative workcenters** (`alternative_workcenter_ids`) — the
  m2m to backup stations. **This is what gives you a rerouting option
  when the primary goes down.**

Open one tile. The per-workcenter form shows the planning-relevant
fields:

- **Costs/hour** (`costs_hour`) — for scheduling, only useful when
  comparing alternatives. SB-SAW is $85/h, SB-EDGE is $65/h, etc.
- **Max panel size** (`x_sbk_max_panel_length_mm`,
  `x_sbk_max_panel_width_mm`) — operations whose cutlist line exceeds
  these can't run here; the MI engine will flag them before they
  reach the floor.
- **Supported materials** (`x_sbk_supported_material_ids`) — the
  scheduler honours this. Don't route melamine panels to a saw set
  up for solid wood.
- **Default setup time** (`x_sbk_default_setup_time_min`) — minutes
  added when a job lands here cold. Operation templates override per
  product family.
- **Changeover time** (`x_sbk_changeover_time_min`) — minutes when
  the next WO requires a different material/finish/tool. At PAINT
  Booth this is the colour-change cost; at SB-EDGE it's the tape
  colour swap.
- **OEE target** (`x_sbk_oee_target`) — default 0.85. Compared against
  actual OEE on the MI dashboard (lesson 3.3).
- **Planning notes** (`x_sbk_planning_notes`) — your scratch space.
  Use it.

## The bottleneck map

Southbrook seeds 8 + 2 workcenters via the seed file. As of today's
config, the bottleneck-flagged stations (`x_sbk_is_bottleneck = True`)
are:

| Code | Name | Station type | Alternative |
|---|---|---|---|
| `SB-SAW` | Panel Saw / CNC Nesting | cutting | — |
| `SB-EDGE` | Edge Bander | edge_banding | — |
| `SB-CNC-BORE` | CNC Boring | cnc | `CNC02` |
| `SB-ASSY` | Carcass Assembly | assembly | — |
| `SB-QC` | Quality Control | quality | — |
| `PAINT` | Paint Booth | finishing | — |
| `CNC02` | CNC Router 02 (Backup) | cnc | `SB-CNC-BORE` |

The CNC pair (`SB-CNC-BORE` <-> `CNC02`) is the only configured
swap. The other bottlenecks have no alternative — they're irreplaceable
in the current shop layout. The ENG01 workcenter is NOT a bottleneck
(`x_sbk_is_bottleneck = False`); it's parallel-friendly because the
engineer can run multiple gate reviews concurrently.

## Your daily flow

**1. Start of shift (15 min): read the bottleneck board.**

- Open **Kitchen Ops -> Workcenter Bottlenecks**.
- Look at each bottleneck-flagged station's `southbrook_pm_inflight_count`.
  A typical "healthy" day: SB-SAW ~6-10, SB-EDGE ~8-14, SB-CNC-BORE
  ~4-8, SB-ASSY ~10-20, PAINT ~3-6, SB-QC ~10-15. **If any single
  bottleneck is above 30, you've over-scheduled it and the cascade is
  already starting.**
- Look at `southbrook_pm_late_count`. Any number > 0 here means the
  station is already behind its deadline. A late count at SB-SAW
  cascades to SB-EDGE three hours later because nothing has tape to
  band. Don't add today's work at a station that's already late
  until you've drained it.
- Look at `southbrook_pm_equipment_alerts`. A `critical` or `offline`
  machine at a bottleneck means you're running with reduced capacity
  even if the workcenter still shows green. Cross-check the
  per-equipment view (under the workcenter, the linked
  `maintenance.equipment` records).

**2. Per release decision (the loop, ~20 per day):**

For each MO in the **Southbrook PM -> Ready Queue** list:

- Open the MO. Look at its routing — which workcenters it touches and
  in what order. The routing is defined by the operation template
  (`southbrook_mrp_kitchen_workcenters`), so it picks the right
  station type automatically. Your job is sequencing, not routing
  selection — the routing already decided.
- Pick the day to release. Use the bottleneck board: if SB-SAW has
  capacity room today but SB-EDGE is full, schedule the saw work for
  today and let the edge banding fall to tomorrow. The system **will
  not refuse** to take the work even when over-loaded; the cascade
  cost is on you to predict.
- Confirm the MO with **Mark as Done -> Confirm**. The MOs land in
  `mrp.workorder` records with their planned start/end times.

**3. Mid-day check (5 min): catch a slipping bottleneck.**

- Refresh **Kitchen Ops -> Workcenter Bottlenecks** around 11:00 and
  14:00.
- A bottleneck's `done_today` count should be tracking to about half
  of its expected daily throughput by noon. If SB-EDGE only finished
  2 work orders by lunch when the day's plan was 12, something is
  wrong — usually setup time, usually a tape colour change you
  didn't see coming.
- Open the in-flight list (click into the workcenter). Sort by
  `date_planned_start`. The work order at the top is what's actually
  running. If it's been running for 3x its planned duration, the
  operator is in trouble — go check on the floor.

**4. End of shift (5 min):**

- Look at `southbrook_pm_late_count` on every bottleneck. The number
  for tomorrow morning will be whatever's left now, plus whatever
  rolls over from today. Plan tomorrow knowing the carryover.
- Open the workcenter's `x_sbk_planning_notes` and add a one-liner
  for the next shift: "SB-CNC-BORE down at 15:30, rerouted next two
  WOs to CNC02 — re-evaluate when machinist returns Monday."

## When a bottleneck breaks down mid-day

This is the hardest situation and the one this lesson exists for.
Walk through it:

1. The operator at SB-CNC-BORE pages: "spindle bearing seized, I'm
   down for the rest of the day." They log downtime on the work
   order (lesson 1.6) and the equipment record's
   `southbrook_condition` flips to `critical`. The
   `southbrook_pm_equipment_alerts` count on SB-CNC-BORE goes from
   0 to 1.
2. Open the workcenter. Read `alternative_workcenter_ids` — SB-CNC-BORE
   lists `CNC02` as a backup (the reciprocal m2m is also set on
   CNC02). The capability tags are compatible because both are
   `x_sbk_station_type = cnc` and the operation template was
   authored to support both.
3. Find every work order at SB-CNC-BORE that hasn't started yet
   today. From the workcenter's in-flight list, select them, **Action
   -> Re-plan** (or move them to CNC02's queue manually — the
   operation template's `alternative_workcenter_ids` makes this
   legal). The work orders move to CNC02's queue, the `workcenter_id`
   updates, and the schedule reflects the new station.
4. CNC02 is the BACKUP — it's slower (likely older), so plan setup
   time generously. Update `x_sbk_planning_notes` on both stations
   so the next shift knows why work is at CNC02 instead of
   SB-CNC-BORE.
5. **Do not flip `x_sbk_is_bottleneck = True` on CNC02.** That's a
   structural decision (which station do we never overload at
   planning time?), not a live-state signal. The MI engine's
   `x_mi_bottleneck_workcenter_id` on `mrp.production` is what
   reflects today's live bottleneck. Those two fields are
   intentionally separate — see "behind the scenes" below.
6. When SB-CNC-BORE comes back up, check the load on CNC02 vs
   SB-CNC-BORE; reroute fresh WOs back to the primary so the backup
   isn't left running at 90% utilisation.

For the bottlenecks WITHOUT a configured alternative (SB-SAW,
SB-EDGE, SB-ASSY, PAINT, SB-QC), the rerouting option doesn't exist.
The realistic actions are:

- **Push the install date.** Talk to the PM, talk to the customer.
  Cabinets late by a day are recoverable; cabinets shipped wrong
  aren't.
- **Subcontract.** Some operations can leave the shop (door
  finishing at a paint partner). The `x_sbk_station_type =
  subcontract` selection exists for this; if you have a subcontract
  routing approved, point the affected MOs at it.
- **Triage which MOs survive.** Tightest-deadline first. The other
  jobs wait. The PM owns this call; you provide the data.

## Common mistakes + how to recover

**"I scheduled 25 MOs through SB-EDGE today and the operator is
showing 14 in their queue. Why are 11 missing?"**

The system applies the `x_sbk_max_panel_length_mm` filter at
operation-template routing time. If 11 of your MOs had a panel
exceeding 2500mm, the routing silently picked a different station
(or failed to route, depending on the template). Open the missing
MOs, look at the routing — they're probably stuck in an unrouted
state. The MI engine should have flagged this with `Oversized
panel` blockers at the gate (lesson 2.2). If they got through the
gate without one, the panel size data is missing or wrong.

**"I rerouted from SB-CNC-BORE to CNC02 but the work order still
shows SB-CNC-BORE on the floor traveler."**

The traveler is generated at MO confirmation, not on every reroute.
Re-print the traveler after rerouting — the new `workcenter_id` is
written to `mrp.workorder` immediately but the PDF artifact is
stale until regenerated.

**"I set `x_sbk_is_bottleneck = False` on SB-EDGE because we got
a second bander, and now the scheduler is overloading both."**

The flag is a TheoryofConstraints structural decision — it says
"never schedule more than this station can deliver." Flipping it
False removes the safety rail; the planner becomes the only thing
preventing overload. Recovery: flip it back to True. Both banders
share the SB-EDGE workcenter record; the right model is one
workcenter with `x_sbk_allows_parallel_jobs = True`, not two
records with the bottleneck flag off.

**"The `southbrook_pm_inflight_count` shows 12 but I count 8 on
the floor."**

The compute counts WOs in `pending` / `waiting` / `ready` /
`progress`. Some of those are sitting in `waiting` because they
have unfinished predecessors; they're not at the station yet.
Filter the workcenter's in-flight list by `state = ready` to see
what's actually claimable now.

**"Late count went from 0 to 4 overnight on SB-ASSY but nothing
was running overnight."**

The compute uses `date_deadline` on the MO, not on the work order.
If the MO's deadline is today and the WO at assembly is the last
remaining step, the count flips at midnight. Recovery: schedule
the assembly work for first thing today, and double-check the MO
deadlines weren't auto-shifted by a confirmation re-run.

## What the system is doing behind the scenes

Two flags carry the word "bottleneck" and they answer different
questions. Get this straight:

- `x_sbk_is_bottleneck` on `mrp.workcenter` is a **configuration**
  flag set at install time in `mrp_workcenter_seed.xml`. It tells
  the planner (you) and the scheduler "this is a structural
  constraint; never overload it." It doesn't change as work runs.
- `x_mi_bottleneck_workcenter_id` on `mrp.production` is a **live**
  field set by the MI engine. For a specific in-flight MO, it
  identifies which workcenter is the constraint today. It changes
  as conditions change.

The four KPI computes on `mrp.workcenter` (`southbrook_pm_inflight_count`,
`southbrook_pm_throughput_today`, `southbrook_pm_late_count`,
`southbrook_pm_equipment_alerts`) live in `southbrook_mrp_pm/
models/mrp_workcenter.py`. They depend on `uid` (so they refresh
when you reload the page) and are not stored — every page-load
re-counts, which is fine because the underlying searches are cheap.

The `alternative_workcenter_ids` field is a native Odoo `mrp.workcenter`
many2many to itself. Southbrook adds the **reciprocity** convention
in the seed file: if A lists B, B lists A. The test
`test_m1_workcenter_fields.py` asserts the round-trip. The operation
template (`southbrook.kitchen.operation.template`) reads BOTH the
primary `workcenter_id` and `alternative_workcenter_ids` when deciding
which station can run an operation step — that's the code path that
lets you re-route without re-writing the routing.

The seven nightly + hourly + 30-min crons (lesson 2.4 covers all six
plus the ECO-proposal cron) are what keep the bottleneck board honest
overnight. In particular, the **MI gate refire** cron re-evaluates
gate checks every hour against in-flight MOs, so an equipment
condition flip at 14:00 surfaces on YOUR queue by 15:00 at the
latest — you don't have to refresh anything.

## Quiz (5 questions, applied)

**1.** You open the bottleneck board at 8:00 AM. SB-SAW shows 22
in-flight, SB-EDGE shows 18 in-flight, SB-CNC-BORE shows 4
in-flight. Which station do you panic about first?

> SB-SAW at 22 in-flight is well above the typical 6-10 range —
> you've over-scheduled cutting, and the cascade hits edge banding
> in three hours. Even though SB-EDGE shows 18 (which is also
> high), SB-SAW is the upstream constraint; if you don't drain it,
> the SB-EDGE number will grow throughout the day as panels
> accumulate. Open SB-SAW's in-flight list, sort by deadline, and
> see if any can roll to tomorrow.

**2.** Mid-day, the operator at SB-CNC-BORE pages that the spindle
seized. CNC02 is configured as an alternative. What's the right
sequence of actions?

> (1) Flip the equipment record's `southbrook_condition` to
> `critical` so the alerts surface. (2) Open the workcenter,
> select the unstarted work orders, reroute them to CNC02
> (the m2m `alternative_workcenter_ids` makes this a legal
> reassignment). (3) Update `x_sbk_planning_notes` on both
> stations explaining the swap. (4) Do NOT flip
> `x_sbk_is_bottleneck` on CNC02 — that's a structural flag.
> (5) When SB-CNC-BORE returns, reroute new WOs back to the
> primary so the backup doesn't get stuck at 90% util.

**3.** A panel listed at 2800mm doesn't appear on SB-EDGE's queue
even though the routing should put it there. Why, and what do you
check?

> SB-EDGE's `x_sbk_max_panel_length_mm` is the gate. If the panel
> exceeds that, the routing doesn't pick SB-EDGE and the operation
> either failed to route or routed to a station with a larger
> capacity envelope. Open the cutlist line, look at the length, and
> compare to the workcenter capacity. The MI engine should have
> raised an `Oversized panel` blocker at the release gate — if it
> didn't, the panel-size data on the cutlist is bogus.

**4.** Mid-day SB-EDGE's `southbrook_pm_inflight_count` is 26 and
`southbrook_pm_late_count` is 5. The PM asks "what's our recovery
plan?" Walk through the conversation.

> First, the bottleneck has no configured alternative — no
> rerouting is available. The recovery options are (a) push install
> dates on the lowest-priority MOs (PM decision, customer call),
> (b) subcontract banding to a partner shop if one is approved
> (`x_sbk_station_type = subcontract` routing), or (c) work the
> overflow as overtime tonight if the operator agrees. Quantify
> each: the 5 late MOs are tomorrow's late count if untouched;
> the 21 not-late but in-flight WOs are the question of whether
> we can drain the queue by end of shift. Give the PM the numbers,
> let them call.

**5.** You see `x_mi_bottleneck_workcenter_id` on a specific MO is
SB-ASSY, but the workcenter's `x_sbk_is_bottleneck` flag on SB-ASSY
is True. Aren't these the same thing?

> No, and it matters. `x_sbk_is_bottleneck = True` is configuration:
> "Southbrook decided at install time that SB-ASSY is structurally
> a bottleneck workcenter." `x_mi_bottleneck_workcenter_id = SB-ASSY`
> for one MO is the live measurement: "for THIS specific MO,
> right now, SB-ASSY is the constraint." They can disagree — an
> MO whose finishing schedule is tight might have its
> live bottleneck at PAINT even though the configured bottleneck
> set includes SB-ASSY. Don't confuse the two.

---

## What this lesson does NOT cover

- The release gate at ENG01 (what gets a job to your queue in the
  first place) -> lesson 2.2.
- The Kitchen Jobs board and project.task readiness states ->
  lesson 2.1.
- The 6 nightly crons that drive readiness, MI refire, analytics,
  planning, DQ, and ECO proposals -> lesson 2.4.
- Reading the MI report once an MO is mid-flight -> lesson 2.5.
- Per-station operator daily flow (the operator's side of the same
  numbers) -> Course 1 lessons 1.2-1.5.
- Native Odoo routing definitions, work order state machine, and
  Manufacturing module setup -> Odoo's own training.
