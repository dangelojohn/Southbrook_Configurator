---
course: 1 — Workcenter Operators
chapter: 1.3
title: CNC Router Operator — Your Daily Flow
duration: 25 minutes
audience: CNC operator working SB-CNC-BORE (primary) and CNC02 (backup)
prereqs: Lesson 1.1 (workcenter orientation), basic Odoo navigation
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_kitchen_tools, southbrook_mrp_pm
---

# CNC Router Operator — Your Daily Flow

## Who this lesson is for

You're the operator standing at the **CNC Boring** machine (workcenter code
`SB-CNC-BORE`, branded as the Biesse Rover) and you're the trained backup on
**CNC Router 02** (`CNC02`, the ShopSabre IS510). Your job is to cut and bore
nested sheets according to the day's cut spec, then hand the cut panels off
to edge banding. You're a bottleneck — `x_sbk_is_bottleneck = True` on
SB-CNC-BORE — so a backed-up queue at your station ripples through the whole
shop. This lesson is what your day looks like.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with your operator account.

> **Kitchen Ops → Workcenters → CNC Boring (SB-CNC-BORE)**

You'll land on the workcenter overview. The day's work orders for SB-CNC-BORE
are at the bottom under **Work Orders**. That's your queue. When the primary
is down or in changeover and you've moved to the backup:

> **Kitchen Ops → Workcenters → CNC Router 02 (CNC02)**

Both stations share the same shop-floor view shape; what changes is the
machine, not the screen.

## What your screen shows

The shop-floor view for SB-CNC-BORE shows:

- **Today's queue** — work orders scheduled to run on the CNC today, in
  the order the planner sequenced them. Each row is one operation step
  from one Manufacturing Order (MO).
- **Current operation** — the one you're working on right now, big
  number, with the panel list expanded.
- **Tool readiness** (`southbrook_tool_readiness_state` on
  `mrp.workorder`) — `not_checked` / `ready` / `warning` / `blocked`.
  Coloured badge. If the badge is red (`blocked`), the system has
  refused to let you tap Start until the missing bit is checked out
  of the tool crib. The detail box names what's missing.
- **Setup time** (`x_sbk_default_setup_time_min` on `mrp.workcenter`) —
  the changeover the planner allowed you between sheets. On SB-CNC-BORE
  this is the tool-change time when the next sheet calls for a
  different bit.
- **Material constraints** (`x_sbk_supported_material_ids`) — your CNC
  handles the sheet stock listed here. If the planner scheduled a
  material your machine isn't set up for, the cell turns amber.
- **Max panel size** (`x_sbk_max_panel_length_mm` /
  `x_sbk_max_panel_width_mm`) — the physical envelope of your bed.
  Oversized sheets shouldn't reach your queue.
- **Bottleneck flag** (`x_sbk_is_bottleneck = True` on SB-CNC-BORE) —
  configuration, not state. Means the planner protects your station
  from overload and the MI engine treats extended idle here as a P0
  issue.
- **Alternative work centers** (`alternative_workcenter_ids`) — wired so
  the scheduler can move a job to `CNC02` when SB-CNC-BORE is in
  changeover or down. You'll see this populated on the form.

## Your daily flow

**1. Start of shift (10 min):**

- Open **Kitchen Ops → Workcenters → CNC Boring (SB-CNC-BORE)**.
- Glance at *Today's queue* — count the work orders. A normal day is
  6–10 nested sheets. If you see 15+, flag the planner before you
  start (see "Common mistakes").
- Tap each of the first 3 work orders and check **Tool Readiness**.
  Anything red means the bit isn't in the crib (or it's in
  `needs_sharpening`). Walk to the tool crib and check out what you
  need before you fire up the spindle, not after.
- Read the **cut spec ID** on the first sheet (the printed traveler
  matches a row in `southbrook.cut.spec`; lesson 1.7 covers reading
  it). Confirm the box thickness, rabbet depth, and drill pattern
  match the bit you've loaded.

**2. Per sheet (the loop):**

For each row in *Today's queue*:

- Tap the row → opens the **Work Order** detail.
- Verify the nest layout printed on the traveler matches the sheet
  loaded on the bed. The panel IDs on the traveler are what the
  banding op downstream will scan; if you mis-nest, banding can't
  find the right panel.
- Tap **Start** — this records the actual start time on the work
  order, changes `state` from `pending` to `progress`, and signals
  the MI dashboard that you've engaged.
- Run the program. The CNC handles the toolpath; your job is
  loading the sheet, monitoring the cut, vacuuming chips, and
  catching tear-out on the edges.
- When the sheet is finished, tap **Done**. Move the cut panels to
  the rolling cart bound for edge banding. The downstream operator
  at SB-EDGE scans the panel IDs and the system links your output
  to their input.
- If the next sheet calls for a different bit, tap **Changeover**
  before starting. This logs `x_sbk_changeover_time_min` against
  the operation so tomorrow's planning math accounts for the swap.

**3. Backup machine handoff (when called):**

If the supervisor tells you to move work to CNC02:

- The planner re-routes a queued WO from SB-CNC-BORE to CNC02 in
  the backend (`alternative_workcenter_ids` makes this a one-click
  move).
- The WO now appears in CNC02's queue. Walk to CNC02, repeat the
  Per-sheet loop. Same screen, different station.

**4. End of shift (5 min):**

- Check *Today's queue* — any rows still open?
  - **Open and partially done** — tap the row, set **completed sheet
    count** so the next-shift operator picks up cleanly.
  - **Open and not started** — leave it; the planner will roll it
    to tomorrow.
- If you broke a bit, ran out of vacuum, or the spindle threw a
  fault, log it as **downtime** (lesson 1.6) with the right equipment
  link before clocking out.

## Common mistakes + how to recover

**"My queue is showing 15 sheets and the day's only 8 hours long."**

The planner ran the schedule without honouring `x_sbk_is_bottleneck`.
Tell the planner. The fix is on the planner side (lesson 2.3); do not
try to grind through 15 sheets — the downstream MO release queue piles
up and the platform raises warnings overnight.

**"I tapped Start, then noticed the bit in the machine doesn't match
the cut spec."**

Tap *Pause* on the work order immediately. Don't cut with the wrong
bit — you'll scrap the sheet. Change the bit, then tap *Resume* and
continue. The pause-to-resume gap is captured in
`mrp.workorder.duration` and the MI engine sees it as a setup event,
not a slow cycle.

**"Tool readiness is blocked because the CNC bit I need is showing
`needs_sharpening`."**

Don't start. The kitchen_tools cron flipped that asset to
`needs_sharpening` overnight because its life ran out. Check out a
backup bit from the same `tool_category` (the readiness check accepts
any descendant of the requirement's category). If no backup exists in
the crib, tell the supervisor and log downtime with reason
`material_not_available` until a sharpened bit is back.

**"I finished a sheet but two panels had blow-out and I scrapped them."**

Tap Done → enter **completed panel count** minus the 2 scrapped ones →
enter a scrap reason. The system raises a `scrap_event` recommendation
for the production manager AND a `cut_spec_audit` recommendation for
the PLM engineer. If the same panel ID blows out repeatedly, the
engineer revises the cut spec (different feed/speed, different bit)
through an ECO — see lesson 1.7.

**"The CNC threw a spindle fault mid-sheet."**

Don't tap Done — that records the sheet as cut. Instead:
- Tap *Pause* on the work order.
- Log **downtime** (lesson 1.6) with equipment ID `Biesse Rover K FT`
  for SB-CNC-BORE or `ShopSabre IS510` for CNC02. Reason
  `machine_breakdown`.
- When the machine is back up, tap *Resume* and continue from the
  paused toolpath if the controller supports it; otherwise mark the
  partial sheet as scrap and re-nest.

## What the system is doing behind the scenes

(Optional reading — the database trail of your taps.)

Every action you take writes to one of these tables:

- **`mrp.workorder`** — the row in your queue. *Start* / *Done* /
  *Pause* / *Resume* update its `state` and its `date_start` /
  `date_finished` fields.
- **`mrp.workorder.duration`** — every Start/Done pair adds a row
  here with `time_start`, `time_stop`, and `loss_id` if there was
  a downtime cause.
- **`southbrook.workorder.tool.consumption`** — when a CNC bit's
  life ticks down, a row here records the consumption against the
  asset, decrements `remaining_life_qty`, and bumps
  `total_usage_qty`. The daily `_cron_maintenance_sweep` reads this
  to know when to flip the asset to `needs_sharpening`.
- **`southbrook.kitchen.workcenter.downtime`** — downtime entries
  you log, linked to the workcenter, equipment, reason, and
  duration.

The `alternative_workcenter_ids` wiring between SB-CNC-BORE and CNC02
is set in `southbrook_mrp_kitchen_workcenters/data/mrp_workcenter_seed.xml`
and is what lets the planner re-route in one click instead of
reconfiguring the routing.

The cut spec your traveler references lives in the single active row
of `southbrook.cut.spec` — see lesson 1.7. The numbers driving your
toolpath (box thickness, rabbet depth, drill pattern reference) are
read from that record by the BoM generator at the moment the MO was
created. If those numbers change, an engineer raised an ECO of
`target_kind = 'cut_spec'`; the chatter on the cut-spec record names
who approved it and when.

## Quiz (5 questions, applied)

**1.** You open *Today's queue* and the first WO shows Tool Readiness
in red with the message "Need: 1 × 8mm Compression Spiral Bit
(category: CNC bits) — found 0 available in crib." What do you do?

> Don't tap Start — the readiness gate will refuse anyway. Walk to
> the tool crib. The named bit may be there but marked
> `needs_sharpening` (still passes `is_available` but readiness
> rejects it). Either pull a sharpened backup from the same category
> or, if none exists, escalate to the supervisor and log downtime
> with reason `material_not_available` until a bit is back in stock.

**2.** A WO is in your queue with a 2750mm sheet. SB-CNC-BORE's
`x_sbk_max_panel_length_mm` is 2500mm. What's the right action?

> Don't load it. The shop-floor view flags the row amber. Tell the
> planner — the cut spec from PLM probably calls for the sheet to be
> reduced at SB-SAW first, or the job needs to go to a station with
> a longer bed. The planner reroutes it.

**3.** You're halfway through the day on SB-CNC-BORE and the
supervisor says "switch to CNC02 — the Biesse is in scheduled
maintenance." What happens to your in-progress WO and your queue?

> The planner uses `alternative_workcenter_ids` to move queued
> (not-started) WOs from SB-CNC-BORE to CNC02. Your in-progress WO
> stays where it is — finish it first on the Biesse, then walk over
> to CNC02 for the next one. Don't try to migrate a started WO
> across machines; mark it Done first or Pause and resume after
> the swap.

**4.** A spindle fault stops the machine for 35 minutes. You pause
the WO, maintenance fixes it, and you resume. The next morning your
supervisor says your cycle time on that WO was 35 minutes over plan.
What happened?

> You forgot to log downtime. The pause-to-resume gap is captured
> on `mrp.workorder.duration`, but without a matching
> `southbrook.kitchen.workcenter.downtime` row linking the fault to
> the `Biesse Rover K FT` equipment, the MI engine attributes the
> 35 minutes to your operator cycle time instead of to a machine
> fault. Fix: log it now (lesson 1.6) — the report re-aggregates.

**5.** A nested sheet finishes and the panel IDs printed on the
traveler don't match the panel-list scan at SB-EDGE. The edge bander
operator is asking what happened. What's the most likely cause and
where do you look?

> You probably loaded the wrong sheet onto the bed (wrong material
> or wrong nest revision). The traveler IDs are generated from the
> cut spec at MO creation; if you ran the right toolpath against a
> different physical sheet, the panel labels off the CNC don't
> match. Look at the sheet barcode against the traveler; if they
> mismatch, the cut sheet is scrap and the MO needs to re-cut.
> Escalate scrap reason + cost via the Done flow as above.

---

## What this lesson does NOT cover

- Native Odoo work-order vocabulary and MRP basics — Odoo's own
  e-learning portal.
- Edge banding (the next stop after CNC) — lesson 1.2.
- Assembly (after banding) — lesson 1.4.
- Downtime logging in detail — lesson 1.6.
- Reading a PLM cut spec — lesson 1.7.
- What the planner does with the bottleneck flag — lesson 2.3.
