---
course: 1 — Workcenter Operators
chapter: 1.5
title: Sander / Finisher — Your Daily Flow
duration: 25 minutes
audience: Sander or finisher rotating between SAND, PAINT, and CURE
prereqs: Lesson 1.1 (workcenter orientation), basic Odoo navigation
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_kitchen_tools, southbrook_mrp_pm
---

# Sander / Finisher — Your Daily Flow

## Who this lesson is for

You're the sander or finisher rotating between three stations: **Sanding
Prep** (`SAND`), **Paint Booth** (`PAINT`), and **Cure / Dry Room** (`CURE`).
You're at the back end of the carcass + door pipeline — assembly hands you
a raw carcass, you sand it, finish it, dry it, and pass it to door hanging
(SB-DOOR) or QC (SB-QC). PAINT is a bottleneck; the colour-changeover
constraint shapes the planner's whole day. SAND and CURE allow parallel
jobs and are designed to absorb flow. This lesson is the practical reality
of moving panels through that three-station chain.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with your operator account.
You'll switch between three menu paths depending on where you're standing:

> **Kitchen Ops → Workcenters → Sanding Prep (SAND)**
> **Kitchen Ops → Workcenters → Paint Booth (PAINT)**
> **Kitchen Ops → Workcenters → Cure / Dry Room (CURE)**

The three stations share screen shape but have very different field
defaults — SAND and CURE allow parallel jobs, PAINT does not; PAINT's
`x_sbk_supported_finish_ids` is the strictest list in the shop.

## What your screen shows

The shop-floor view shows (with station-specific notes):

- **Today's queue** — the WOs scheduled at this station today. At PAINT
  the planner groups by colour to minimise changeover; at CURE you'll
  see many WOs in parallel.
- **Setup time** (`x_sbk_default_setup_time_min` on `mrp.workcenter`) —
  at SAND, this is grit-paper change. At PAINT, this is the spray-gun
  flush + cup change between colour batches. At CURE, this is
  essentially zero (panels just go on racks).
- **Changeover time** (`x_sbk_changeover_time_min`) — this is the big
  one at PAINT. A colour swap from white to dark walnut is 30+
  minutes of gun cleaning. The planner's `x_sbk_planning_notes` on
  PAINT spell it out: "Paint colour changeover is the dominant
  scheduling constraint — group like-colours into runs whenever
  possible."
- **Supported finishes** (`x_sbk_supported_finish_ids` on
  `mrp.workcenter`) — m2m to `southbrook.kitchen.finish`. **PAINT
  only handles the finishes seeded here.** If your shop hasn't seeded
  solvent finishes against PAINT, the planner won't route solvent
  jobs to PAINT — they'd go to a subcontractor (station type
  `subcontract`) instead.
- **Allows parallel jobs** (`x_sbk_allows_parallel_jobs`):
  - SAND: True — multiple sanders work side by side.
  - PAINT: False — one spray job at a time.
  - CURE: True — many panels drying on racks at once. The cure
    room's `x_sbk_planning_notes` notes that
    `finish.cure_time_buffer_min` drives how long each part stays
    here.
- **Bottleneck flag** (`x_sbk_is_bottleneck`):
  - SAND: False.
  - PAINT: True.
  - CURE: False.
- **Quality notes** (`x_sbk_quality_notes` on `mrp.workcenter`) —
  station-specific defect modes wired into the M3 `mi.check` flow.
  At SAND it lists swirl marks, missed corners, grit-skip. At PAINT
  it lists orange peel, runs, fish-eye.

## Your daily flow

**1. Start of shift (10 min):**

- Open **Kitchen Ops → Workcenters → SAND** (or wherever your day
  starts).
- Check the **queue length** at all three stations. SAND with 12
  carcasses and PAINT with 4 batches is normal. PAINT with 12
  batches across 6 colours is a colour-grouping problem; flag the
  planner.
- At PAINT specifically: open the first 2 WOs and check the
  **finish** field. If two consecutive WOs are different colours and
  could be reordered to land same-colour back-to-back, suggest it to
  the supervisor before you mix the first cup.

**2. SAND — per carcass (the loop):**

For each row in *Today's queue*:

- Tap the row → opens the **Work Order** detail. The panel list
  shows what's on your cart.
- Verify the carcass has the assembly Done stamp (from SB-ASSY,
  lesson 1.4). If not, escalate — don't sand an in-progress
  carcass.
- Tap **Start**.
- Run the grit sequence the operation template specifies (typically
  120 → 180 → 220 for stain-grade, 120 → 180 for paint-grade). The
  operation template's `complexity_factor` drives how much time the
  planner allowed.
- Tap **Done** when the carcass is at the target grit and visually
  clean.
- Push the carcass to the PAINT staging area, grouped by colour
  (look at the next WO's finish field).

**3. PAINT — per batch (the loop):**

For each row in *Today's queue*:

- Confirm the **finish** field matches the colour currently loaded
  in the gun. If it doesn't, tap **Changeover** before Start. The
  changeover logs `x_sbk_changeover_time_min` and the planner's
  next-day prediction stays honest.
- Tap **Start**.
- Spray the carcass per the finish's spec (number of coats, flash
  time between coats).
- When the batch is done, tap **Done** and move the rack to CURE.
- If a defect (run, orange peel, fish-eye) shows up, the QC flow
  (lesson 1.4-adjacent — the `southbrook.mi.check` model) lets
  you record `result = rework` and the WO loops back. You don't
  tap Done on a defect batch; you tap Block + raise the check.

**4. CURE — manage the racks:**

CURE is different — you're not running an operation, you're
managing time. Each WO at CURE has a cure-time clock that started
when PAINT marked it Done.

- The CURE shop-floor view shows each rack with a countdown to
  cure-time expiry (`finish.cure_time_buffer_min` drives the
  countdown).
- When a rack's clock hits zero, the WO at CURE is eligible to be
  marked Done. Push that rack out, mark the WO Done, and load the
  next wet rack into the vacated slot.
- Parallel jobs at CURE means many WOs are in `progress` at the
  same time. Don't confuse "this rack is dry" with "this WO is
  next in queue."

**5. End of shift (5 min):**

- Walk SAND → PAINT → CURE one more time. Anything still in
  `progress`?
- For CURE specifically: panels still wet after your shift will
  finish curing on the night shift — leave the WOs in `progress`
  and the next-shift finisher will mark them Done.
- Log downtime (lesson 1.6) for any booth fault, gun clog, or
  compressor failure before clocking out.

## Common mistakes + how to recover

**"PAINT's queue has 6 colours and 12 batches — the planner gave me a
nightmare."**

Tell your supervisor. The fix is on the planner side (Course 2,
lesson 2.3): the planner groups by colour. PAINT's
`x_sbk_planning_notes` literally says to do this. If the planner
forgot the bottleneck flag honoured during the schedule run, the
re-run will sequence you correctly. Meanwhile sort the physical carts
into colour groups yourself so when the re-run lands you can blast
through them.

**"A WO at PAINT has `finish_id` set to a solvent finish, but PAINT's
`x_sbk_supported_finish_ids` only lists waterborne. Why is it even in
my queue?"**

It shouldn't be — the scheduler filters on supported finishes when it
picks a station. If it's there anyway, the planner overrode the
scheduler manually. Don't spray it. Tap *Block* on the WO with reason
"finish not supported at PAINT — should route to subcontract." The
system raises a `materials_blocked` recommendation overnight. The
production manager reviews and either reroutes to a finishing
subcontractor (`station_type = 'subcontract'`) or sources a different
finish.

**"A carcass came to me at SAND but the `x_sbk_kitchen_project_id` on
the MO has been revoked — it's not in `in_production` anymore."**

That means ENG01 (Design Review) pulled the kitchen project back to
`approved`. The WO disappears from your active queue but the physical
carcass is sitting at your bench. Don't sand. Park it on the hold
shelf and let your supervisor know. The kitchen project will reappear
in your queue when ENG01 re-releases.

**"I tapped Done at PAINT but the carcass had a run I didn't see
until 10 minutes later."**

Undo Done — available for 10 minutes. After that, the WO is
permanently `done` from the PAINT perspective. The recovery is:
manually create a rework WO at SAND + PAINT through the QC flow
(`mi.check.result = rework`). The system creates a new pair of WOs
linked back to the original via `x_sbk_rework_workorder_id` on the
mi.check record, and the cost rolls up to your supervisor's rework
report.

**"The cure timer says 240 min but the supervisor wants the carcass
pushed to SB-DOOR after 180 — is it OK to short-cycle?"**

No. The cure time comes from `finish.cure_time_buffer_min` and is
chemistry, not preference. Short-cycling causes paint marring at
SB-DOOR when the door is mounted against the still-tacky surface.
If the supervisor insists, document it (`notes` on the WO) and let
the production manager carry the QC risk; the system will not stop
you from tapping Done early but the chatter will record the deviation.

## What the system is doing behind the scenes

(Optional reading — the database trail.)

Every action you take writes to one of these tables:

- **`mrp.workorder`** — your queue rows. `state` flips
  pending → progress → done as you tap.
- **`mrp.workorder.duration`** — Start/Done pairs add rows here.
- **`southbrook.mi.check`** — the QC step. When you mark a defect
  through the check, this row records the defect type, severity
  (minor / major / critical), and result (pass / fail / rework /
  hold). If result is `rework`, the computed
  `x_sbk_rework_required` is True and the system creates a rework
  WO linked back via `x_sbk_rework_workorder_id`.
- **`southbrook.kitchen.finish`** — the master record for each
  finish. `cure_time_buffer_min` drives the CURE clock; the
  finish's complexity_factor scales the operation template's
  duration math at PAINT.

The PAINT bottleneck flag (`x_sbk_is_bottleneck = True`) and the
False parallel-jobs flag together mean the planner treats PAINT as
the lowest-throughput station in the shop and groups colour batches
aggressively. This is the single most impactful scheduling decision
of the day — when the manager looks at why an MO is late, PAINT is
the first place she checks.

CURE's high parallel capacity + non-bottleneck status mean CURE will
almost never be on the manager's critical path. It absorbs flow time,
not throughput. Your job at CURE is timing, not speed.

## Quiz (5 questions, applied)

**1.** At PAINT, you finish a white batch and the next WO in queue is
dark walnut. The system shows a `x_sbk_changeover_time_min` of 30
minutes on PAINT. Do you tap Changeover before Start on the walnut
WO?

> Yes. Tapping Changeover logs the 30 minutes against the operation
> as setup (not running) time. If you skip it and just tap Start, the
> 30 minutes you spent flushing the gun lands on your cycle-time
> stat as if you were spraying slowly. OEE drops, the manager asks
> why, and the data lies.

**2.** A solvent-finish WO appears in PAINT's queue. PAINT's
`x_sbk_supported_finish_ids` doesn't include any solvent finishes.
What do you do, and what's the underlying database fix?

> Don't spray. Tap *Block* on the WO with reason "finish not
> supported at PAINT — should route to subcontract" — this raises a
> `materials_blocked` recommendation. The underlying fix is either
> (a) add the solvent finish to PAINT's `x_sbk_supported_finish_ids`
> if the booth has been upgraded, or (b) the planner reroutes to a
> subcontractor workcenter (`station_type = 'subcontract'`). The
> supervisor + production manager decide which.

**3.** You're at CURE and 4 racks are in `progress` at the same time
on different MOs. How does the system track which rack is whose,
and what does `x_sbk_allows_parallel_jobs = True` mean here?

> Each WO is its own `mrp.workorder` row at CURE; the parallel flag
> means the scheduler is willing to start multiple WOs at once
> without queuing them. The `mrp.workorder.duration` table tracks
> each WO's Start/Done independently. The physical rack-to-WO
> mapping is on you — that's a sticky label on the rack, not in the
> database. If you mix racks, you'll mark the wrong WO Done at the
> wrong time.

**4.** Your supervisor says SAND ran at 78% OEE yesterday, below the
0.85 target. You and the other sander were busy all day. What's the
most likely explanation?

> Two candidates: (a) you both forgot to tap Start when you began a
> WO and tapped only Done at the end, so the duration looks like
> "instant" and the rest of the day looks idle; (b) you ran rework
> through SAND that wasn't logged as rework, so the time appears
> as fresh production (which scopes into OEE's "good output"
> denominator). Fix going forward: tap Start before grit-up, and
> if a rework comes through SAND from PAINT, use the QC flow so
> the rework time is attributed.

**5.** The cure clock on a WO at CURE just hit zero, but the carcass
on the rack physically feels tacky. What do you do?

> Don't mark Done. The clock is a model derived from
> `finish.cure_time_buffer_min` and is the *minimum* the engineer
> set; humidity, temperature, and coat thickness can extend real
> cure time. Trust your finger. Log a downtime entry against CURE
> with reason `other` and notes "cure time exceeded model — humid
> day" so the engineer can update the finish's
> `cure_time_buffer_min` if it's a pattern.

---

## What this lesson does NOT cover

- Native Odoo work-order vocabulary and MRP basics — Odoo's own
  training portal.
- Assembly (your upstream) — lesson 1.4.
- Door hanging at SB-DOOR (your downstream for fronts) — lesson 1.4
  covers the SB-DOOR rotation.
- Quality control at SB-QC — covered in Course 3.
- Downtime logging — lesson 1.6.
- Reading PLM cut specs for finish call-outs (the finish_id and
  cure_time_buffer_min on the spec) — lesson 1.7.
- The colour-grouping algorithm the planner uses — Course 2,
  lesson 2.3.
