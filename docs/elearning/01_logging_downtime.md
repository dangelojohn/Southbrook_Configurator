---
course: 1 — Workcenter Operators
chapter: 1.6
title: Logging Downtime — Every Operator, Every Shift
duration: 20 minutes
audience: Every shop-floor operator
prereqs: Lesson 1.1 (workcenter orientation), your station's role lesson (1.2–1.5)
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_pm
---

# Logging Downtime — Every Operator, Every Shift

## Who this lesson is for

You're a shop-floor operator and your machine just stopped — or you stopped,
or you're waiting on a part, or a tool changeover is taking longer than
planned. This lesson is how you log that idle time so that **(a)** it
doesn't depress your personal cycle-time stat, and **(b)** your manager
sees a clean picture of where the shop loses time. Every operator does
this; the model is the same regardless of which station you work.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with your operator account.

> **Manufacturing → Operations → Southbrook Kitchen → Work Center Downtime**

That's the master list of every downtime entry in the shop. To raise a new
entry from your workcenter screen, the workcenter form has a *Log Downtime*
button that pre-fills the workcenter field — that's the faster path during
a shift.

> **Kitchen Ops → Workcenters → (your station) → [Log Downtime]**

The list view supports search by workcenter, reason, and date; the form
view has the state machine buttons (Start / Close / Cancel).

## What your screen shows

The downtime form (model: `southbrook.kitchen.workcenter.downtime`) shows:

- **Description** (`name`) — short label for the event. Defaults to
  "Downtime" — overwrite with something useful like "HOMAG feed roller
  jam" or "Out of edge tape — white melamine."
- **State** (`state`) — `draft` → `active` → `closed` (or `cancelled`).
  Tracked on the chatter. `draft` is when you're typing it; `active`
  is when the downtime is *happening now* (clock running);
  `closed` is when it's over and the duration is final.
- **Work Center** (`workcenter_id`) — required. Pre-filled if you
  opened from the workcenter screen.
- **Work Order** (`workorder_id`) — optional. Fill in if the downtime
  was tied to a specific WO running at the time (the machine jammed
  mid-WO). The system auto-links the production order through the
  related field `production_id`.
- **Reason** (`reason`) — required. A fixed list of 13 codes:
  - `material_not_available` — out of stock at your station
  - `drawing_issue` — cut spec / drawing problem
  - `machine_breakdown` — mechanical fault
  - `tool_change` — swapping bits / blades
  - `setup_time` — initial setup on a fresh MO
  - `color_finish_changeover` — paint colour swap at PAINT
  - `waiting_previous_operation` — upstream WO isn't done
  - `waiting_quality_approval` — held at QC
  - `rework` — looping back from a defect
  - `operator_unavailable` — you stepped away
  - `subcontract_delay` — outside vendor late
  - `maintenance` — planned, scheduled service
  - `other` — anything that doesn't fit
- **Start / End** (`date_start` / `date_end`) — timestamps. Start
  defaults to "now"; end is filled by Close.
- **Duration (min)** (`duration_min`) — computed from start/end but
  editable, so you can backfill an estimate if you forgot to start
  the timer.
- **Downtime Cost** (`downtime_cost`) — computed:
  `duration_min / 60 × workcenter.costs_hour`. Read-only. This is
  what rolls up to the manager's Pareto chart.
- **Logged By** (`responsible_id`) — defaults to you.
- **Notes** (`notes`) — free-form. Describe what happened. The
  next-shift operator + the maintenance technician read this.

## Your daily flow

**1. The moment the line stops:**

- From your workcenter screen, tap *Log Downtime*. A new draft entry
  opens with workcenter pre-filled.
- Fill in **Reason** — the dropdown of 13. Pick the most specific.
- If a specific WO was running, fill in **Work Order**. Otherwise
  leave it blank.
- Tap **Start**. The `state` flips from `draft` to `active`, and
  `date_start` is stamped to now.
- Walk away. Fix the problem. Don't fiddle with the form while the
  clock is running.

**2. When the problem is fixed:**

- Come back to the entry (still open on your tablet, or find it in
  the active filter on the list view).
- Tap **Close**. The `state` flips to `closed`, `date_end` is
  stamped to now, and `duration_min` + `downtime_cost` compute
  automatically.
- Optionally add a **Notes** entry — what was the root cause? What
  did you do? This is what the maintenance technician reads when
  the same fault recurs.

**3. Backfilling (when you forgot to start the timer):**

- Open the list view → *Create*.
- Fill in workcenter + reason + the **Start** and **End** timestamps
  manually (your best estimate).
- Save in `draft`. The duration field computes from your timestamps
  but is editable, so adjust if your estimate is rough.
- Tap **Close** directly to skip the active state. The entry is
  immediately final.

**4. End of shift:**

- Open the list view, filter "Logged By = me" + "Today."
- Every entry should be `closed` or `cancelled`. Any in `active` is
  still ticking, inflating its duration. Close them before clocking
  out.

## Common mistakes + how to recover

**"I had a 47-minute machine fault and I forgot to log downtime. The
next morning my cycle-time stat for that WO is awful."**

Backfill the downtime entry. Open the list view → Create → set the
workcenter, reason `machine_breakdown`, equipment + workorder fields,
and the actual start/end times (within 10 minutes is fine — the MI
engine doesn't penalise small estimation error). Save and close.
The downtime aggregator re-reads the table on its next cron run and
your cycle-time number recomputes.

**"I logged downtime but picked the wrong reason."**

Open the entry — `reason` is editable while the state is `draft` or
`active`. If it's already `closed`, the field is still editable but
the chatter records the change so the manager can see the
correction. The Pareto chart re-reads on the next refresh.

**"I started downtime but never closed it. It's been three days."**

The entry is still `active` and is showing an inflated duration on
the manager's report. Open it, tap *Close* — `date_end` is stamped
now (huge value), then manually edit `duration_min` to the real
number. The `_check_non_negative_duration` constraint enforces
positive duration; the chatter records the manual override.

**"The downtime cost looks wrong — it's $0."**

`downtime_cost = duration_min / 60 × workcenter.costs_hour`. If the
workcenter has `costs_hour = 0` (often true for non-machine stations
like ENG01), the cost computes to zero. That's correct — downtime
at a free-cost station has no dollar impact, only flow impact. The
manager's Pareto chart shows count + duration alongside cost so the
zero-cost stations still surface.

**"My downtime entry's `duration_min` is showing 0 even though I
filled in start and end."**

Check the constraint: `date_end` must be strictly after `date_start`,
not equal. If you tapped Start then Close within the same second,
the duration computes to zero. Edit `date_start` back by a minute
and save — the system uses the more accurate manual override.

## What the system is doing behind the scenes

(Optional reading — the database trail.)

When you tap Start on a downtime entry, the model
`southbrook.kitchen.workcenter.downtime` writes:

- A new row with `state = 'active'`, `date_start = now()`,
  `date_end = null`, `responsible_id = <you>`.
- The chatter (mail.thread) records the state change.

When you tap Close:

- The row updates `state = 'closed'`, `date_end = now()`.
- `_compute_duration` fires and computes `duration_min` from the
  delta.
- `_compute_downtime_cost` fires and computes `downtime_cost` from
  `duration_min / 60 × workcenter.costs_hour`.

The MI engine's nightly aggregator reads this table grouped by
`workcenter_id` + `reason` to produce the **downtime-by-cause Pareto
chart** the manager sees. Your machine-attributed downtime (reason
`machine_breakdown`, `tool_change`, `maintenance`, `subcontract_delay`)
is excluded from your *personal* cycle-time stat — that's the
point. The MI engine's cycle-time-variance calculation reads
`mrp.workorder.duration` rows and subtracts any overlapping downtime
windows linked to the same `workorder_id`.

Operator-attributed reasons (`operator_unavailable`, partial
`rework`) DO land on your cycle-time stat — which is also correct:
they reflect human factors, not machine factors.

If you link the downtime to a `workorder_id`, the related
`production_id` field auto-populates so the manager can search
"all downtime on MO/0042" and see exactly when each fault hit
during that order's lifecycle.

## Quiz (5 questions, applied)

**1.** The HOMAG edge bander throws an error mid-WO. You pause the WO,
maintenance fixes the feed roller in 42 minutes, you resume. You forget
to log downtime. The next day your supervisor says your cycle time
on that WO is 42 minutes over plan. Why and how do you fix it?

> The pause-to-resume gap is captured on `mrp.workorder.duration`,
> but without a `southbrook.kitchen.workcenter.downtime` row with
> reason `machine_breakdown` linking the workorder + the workcenter,
> the MI engine can't subtract the fault window from your cycle
> time. Fix: create the downtime entry now — workcenter `SB-EDGE`,
> reason `machine_breakdown`, the actual start + end (your best
> estimate), and tie it to that workorder_id. The MI re-aggregator
> on the next cron run will recompute and the 42 minutes will drop
> off your cycle-time stat.

**2.** You're at PAINT swapping from white to walnut. You don't bother
logging downtime because "it's just a colour change, the system knows
the changeover time." What's the consequence?

> The `x_sbk_changeover_time_min` configured on PAINT is the *planned*
> changeover — the planner used it to allow time in the schedule.
> But it's not automatically logged as actual; the system relies on
> you tapping *Changeover* on the WO (which writes to
> `mrp.workorder.duration` with the loss attribution) or logging a
> downtime entry with reason `color_finish_changeover`. Without one
> of those, the actual changeover lands on your spray cycle-time
> stat. OEE drops.

**3.** You log a downtime entry, tap Start, then realise the line is
actually fine — false alarm. What do you do?

> Tap *Cancel*. The state flips to `cancelled`. The entry stays in
> the database for audit (so a recurring "false alarm" pattern is
> visible) but is excluded from duration and cost aggregates.

**4.** A downtime entry shows `duration_min = 0` and `downtime_cost
= $0.00` even though you remember the line was down for 25 minutes.
What happened, and what do you do?

> Two possibilities: (a) `date_start = date_end` because you tapped
> Start and Close within the same second — fix by editing
> `date_start` back 25 minutes; or (b) you cancelled instead of
> closed — open the entry, check `state`. If it's `cancelled`,
> reopen by editing `state` to `closed` and set the timestamps.
> The duration recomputes.

**5.** Your manager opens the downtime Pareto for last month. The
top reason is `waiting_previous_operation` at SB-EDGE for 17 hours
of total lost time. What does that mean about the shop, and which
station's data does she go look at next?

> SB-EDGE was idle waiting on SB-SAW or SB-CNC-BORE to deliver cut
> panels. The bottleneck this month was upstream of the edge
> bander, not at it. She'd open SB-SAW's downtime and OEE reports
> next — probably finding either machine_breakdown at SB-SAW or
> material_not_available (the cutting station ran out of sheet
> stock). The edge bander operator wasn't slow; the cutting
> station starved them. The fix is upstream.

---

## What this lesson does NOT cover

- Native Odoo work-order vocabulary and MRP basics — Odoo's own
  training portal.
- Your station's daily flow — your role-specific lesson (1.2–1.5).
- How the MI engine processes downtime into reports — Course 3,
  lesson 3.1 (MI dashboards) + 3.3 (OEE).
- The QC flow and rework loops — covered alongside the finisher
  lesson and Course 3.
- How the planner uses your downtime to re-tune cycle-time
  estimates for tomorrow's schedule — Course 2, lesson 2.3.
