---
course: 1 — Workcenter Operators
chapter: 1.2
title: Edge Banding Operator — Your Daily Flow
duration: 25 minutes
audience: Edge Banding Operator (works the HOMAG edge bander at workcenter SB-EDGE)
prereqs: Lesson 1.1 (workcenter orientation), basic Odoo navigation
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_pm
---

# Edge Banding Operator — Your Daily Flow

## Who this lesson is for

You're the operator standing at the **HOMAG Edge Bander** (workcenter code
`SB-EDGE`). Your job is to apply edge tape to cabinet panels that come off
CNC and pass them down the line to assembly. You're a bottleneck — if
panels pile up at your station, the whole shop slips. This lesson is the
practical reality of using the Southbrook MRP system from your station.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with your operator account,
then:

> **Kitchen Ops → Workcenters → Edge Bander (SB-EDGE)**

You'll see the workcenter overview. The day's work orders for your machine
are listed at the bottom under **Work Orders**. That's your queue.

If you prefer the shop-floor view (large buttons, touchscreen-friendly):

> **Kitchen Ops → Shop Floor → SB-EDGE**

Both views read the same data. The shop-floor view is what you'll use
day-to-day; the workcenter overview is what your supervisor uses when
they're standing next to you.

## What your screen shows

The shop-floor view for SB-EDGE shows:

- **Today's queue** — the work orders scheduled to run on the edge bander
  today, in the order the planner sequenced them. Each row is one
  operation step from one Manufacturing Order (MO).
- **Current operation** — the one you're working on right now, big
  number, with the panel list expanded.
- **Setup time** (`x_sbk_default_setup_time_min` on `mrp.workcenter`) —
  for SB-EDGE this is the changeover time when you switch from one
  edge tape colour/material to another. Logged on the workorder so
  planning can predict realistically.
- **Material constraints** (`x_sbk_supported_material_ids`) — your edge
  bander handles melamine, MDF, and particleboard. If the planner
  scheduled solid-wood panels here by accident, the cell turns amber
  and the panel doesn't run.
- **Max panel size** (`x_sbk_max_panel_length_mm` /
  `x_sbk_max_panel_width_mm`) — SB-EDGE has limits; oversize panels
  shouldn't be in your queue and will be flagged.
- **Bottleneck flag** (`x_sbk_is_bottleneck = True` for SB-EDGE) — this
  is *configuration*, not *current state*. It means **planning treats
  your station as the constraint that decides the day's max throughput**.
  You'll see this flag honoured in two places: (a) the planner avoids
  parallel routes through you; (b) the MI report flags an extended idle
  on your machine as a P0 issue.

## Your daily flow

**1. Start of shift (5 min):**

- Open **Kitchen Ops → Shop Floor → SB-EDGE**.
- Look at *Today's queue* — count the work orders. A normal day is 8–14
  rows. If you see 25+, the planner overloaded you; flag it before you
  start (see "Common mistakes" below).
- Check the *Material* column on the first 3 work orders. If two
  consecutive ones use the **same edge tape colour**, the planner has
  already sequenced you to avoid changeover; if not, ask your supervisor
  whether to resequence.

**2. Per work order (the loop):**

For each row in *Today's queue*:

- Tap the row → opens the **Work Order** detail.
- Verify the panel list matches the kit that's physically at your station.
  Each panel has a **cut spec** label (printed at CNC) showing the
  panel ID and which edges need tape. Mismatch → escalate, don't band.
- Tap **Start** — this records the actual start time on
  `mrp.workorder.duration` and changes the work order state to
  `progress`. Your supervisor's MI dashboard now shows you've engaged the
  job.
- Apply the tape. The HOMAG handles the actual machining; your job is
  loading panels, watching the feed, and catching defects.
- When the kit is done, tap **Done**. This records actual end time and
  the system computes your actual cycle time vs the planned cycle time.
  If actual is more than 20% over plan, the MI engine will file a
  `slow_workorder` recommendation overnight for your supervisor to review.
- If the next work order uses a different tape colour, tap **Changeover**
  before starting it. This logs `x_sbk_changeover_time_min` against
  the operation so the planner's next-day predictions stay honest.

**3. End of shift (5 min):**

- Check *Today's queue* — any rows still open?
  - **Open and partially done** — tap the row, set the **completed panel
    count** so the system knows how many panels remain. The next-shift
    operator picks up from where you stopped.
  - **Open and not started** — leave it; the planner will roll it to
    tomorrow.
- If you broke a tape, ran out of consumables, or the machine jammed,
  log it as **downtime** (see lesson 1.6) before clocking out.

## Common mistakes + how to recover

**"My queue is showing 25 rows and the day's only 8 hours long."**

The planner ran an unconstrained schedule against you. Tell your
supervisor. The fix is on the planner side (lesson 2.3): the planner
re-runs scheduling with the bottleneck flag honoured. Do **not** try to
work through 25 rows — the MO release queue will pile up downstream
and the platform will start raising warnings.

**"The work order says HOMAG-supported tape but the cut spec on the
panel calls for a tape colour I don't have in stock."**

Don't band the wrong colour to keep the line moving. Open the work
order → click *Block* (in the kebab menu) and add a one-line reason. The
system files a `materials_blocked` recommendation overnight for the
production manager. The work order stays in your queue but is excluded
from your daily count.

**"I tapped Start on the wrong row."**

Tap the row again → *Undo Start*. Available for 5 minutes after the
start tap. After 5 minutes, you need to mark it Done with `notes:
"misclick — actual not run"` and the planner will reschedule. The MI
engine ignores undone-as-misclick rows so it doesn't pollute your stats.

**"I finished a kit but the cut spec says 6 panels and I only banded 5
because one was damaged at CNC."**

Tap Done → enter **completed panel count: 5** → enter the **scrap
reason** for the missing panel. The system raises a `scrap_event`
recommendation for the production manager AND a `cut_spec_audit`
recommendation for the PLM engineer, so the engineer can decide if
the cut spec needs a tolerance update.

**"The HOMAG threw an error mid-kit and I'm not sure if I should hit
Done."**

Don't hit Done — that records the kit as complete. Instead:
- Tap *Pause* on the work order.
- Log **downtime** with the equipment ID `HOMAG Edge Bander` (see
  lesson 1.6).
- When the machine is back up, tap *Resume* and continue where you
  stopped. The system stitches the two durations together and the
  downtime is excluded from your cycle-time stat.

## What the system is doing behind the scenes

(Optional reading — useful if you want to understand what your taps are
writing into the database.)

Every action you take on the shop-floor view writes to one of three
tables:

- **`mrp.workorder`** — the row in your queue. *Start* / *Done* /
  *Pause* / *Resume* update its `state` (`pending → progress → done`)
  and its `date_start` / `date_finished` fields.
- **`mrp.workorder.duration`** — every Start/Done pair adds a row here
  with `time_start`, `time_stop`, and `loss_id` if there was a
  downtime cause. The MI engine reads these to compute OEE and cycle
  time variance.
- **`southbrook_kitchen_workcenter_downtime`** (Southbrook-custom) —
  when you log downtime, a row is added here linking the workcenter,
  the equipment, the reason category (mechanical / electrical /
  consumable / scheduled), and the duration. This is what feeds the
  manager's downtime-by-cause Pareto chart.

The bottleneck flag (`x_sbk_is_bottleneck = True` on SB-EDGE) is a
**configuration** on the workcenter record set at install time
(`southbrook_mrp_kitchen_workcenters/data/mrp_workcenter_seed.xml`).
Nothing you do on the shop floor changes it. It's what makes the
planner's algorithm decide that your station is the throughput
constraint of the shop, and what makes the MI engine treat your idle
minutes as P0.

## Quiz (5 questions, applied)

**1.** You start your shift, open *Today's queue* on SB-EDGE, and see 8
rows. Rows 1, 2, and 4 all use white melamine tape; row 3 uses black
melamine. What's the right action?

> Suggest to your supervisor that rows 3 and 4 be swapped, so you run
> all three white rows back-to-back and do the black tape change only
> once. Saves one changeover (~15 min). Don't swap them yourself —
> the planner has the authority and the audit trail.

**2.** You tap **Start** on a work order, realise 30 seconds later it's
the wrong row, and look for the Undo button. Where is it?

> The same row in your queue — the *Start* button has flipped to
> *Undo Start* for the first 5 minutes. After 5 minutes, you must mark
> Done with a `misclick` note instead and ask the planner to reschedule.

**3.** A work order in your queue is for a panel that's 2800mm long.
SB-EDGE's `x_sbk_max_panel_length_mm` is 2500mm. What happens, and what
do you do?

> The shop floor view flags the row amber. **Do not start it.** Tell
> your supervisor — the cut spec from PLM probably calls for the long
> panel to be banded in two passes, or the panel needs to be banded on
> the larger HOMAG outside your station. The planner will reroute it.

**4.** The HOMAG jams mid-kit. You pause the work order and the
machine is down for 47 minutes while maintenance fixes a feed roller.
Which of these do you do?

> (a) Resume the work order — that's it. The pause-to-resume gap is
> already captured. But **also** log a downtime entry with cause
> `mechanical` and equipment `HOMAG Edge Bander`. Without the
> downtime entry, the 47 minutes lands on YOUR cycle-time stat
> instead of being attributed to a machine fault.

**5.** Your supervisor says "the MI dashboard shows your OEE was 64%
yesterday, target is 78% — what happened?" You look at the work orders
you ran and they all finished on time. What's most likely wrong?

> You likely didn't log changeovers between tape colours, so the
> system thinks every minute between Start and Done on consecutive
> different-colour rows was "running" when in fact you were swapping
> tape rolls. OEE = available time / good output, so unlogged
> changeovers depress it. Lesson: tap **Changeover** between
> different-tape rows, every time.

---

## What this lesson does NOT cover

- General Odoo navigation, work-order vocabulary, and MRP basics →
  Odoo's own native eLearning track.
- Downtime logging details → lesson 1.6.
- Reading a cut spec from PLM → lesson 1.7.
- What happens to your work orders after Done — pick-and-pass to
  assembly → lesson 1.4.
- What the planner does with your station's data — lesson 2.3.
