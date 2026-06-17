---
course: 1 — Workcenter Operators
chapter: 1.4
title: Assembler — Your Daily Flow
duration: 25 minutes
audience: Cabinet assembler working SB-ASSY (carcass) and SB-DOOR (door hanging)
prereqs: Lesson 1.1 (workcenter orientation), basic Odoo navigation
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_pm
---

# Assembler — Your Daily Flow

## Who this lesson is for

You're the assembler at **Carcass Assembly** (workcenter code `SB-ASSY`) and
you may also rotate through **Door Hanging** (`SB-DOOR`). Your job is to
take banded panels off the cart from SB-EDGE, square them up with the
hardware kit pulled by SB-HW, glue and screw the carcass together, and pass
the finished box to sanding. SB-ASSY is a bottleneck — but it's also one of
the few stations where `x_sbk_allows_parallel_jobs = True`, so two assemblers
can work the same MO at once. This lesson is how that works in practice.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with your operator account.

> **Kitchen Ops → Workcenters → Carcass Assembly (SB-ASSY)**

You'll see the workcenter overview. Your queue is the **Work Orders** list
at the bottom. If you're rotating to door hanging:

> **Kitchen Ops → Workcenters → Door Hanging (SB-DOOR)**

Same screen shape, different station, different parallel rules.

## What your screen shows

The shop-floor view for SB-ASSY shows:

- **Today's queue** — work orders scheduled to assemble today. Each row
  is one operation step on one MO; one MO can have its assembly step
  split across two operators because `x_sbk_allows_parallel_jobs` is
  True at SB-ASSY.
- **Current operation** — the carcass you're building right now.
- **Setup time** (`x_sbk_default_setup_time_min` on `mrp.workcenter`) —
  the minutes the planner reserved for jig setup at the start of a fresh
  MO. Carcass jig changes between a base cabinet and a tall pantry are
  the dominant case.
- **Material constraints** (`x_sbk_supported_material_ids`) — your
  assembly bench can handle any carcass material the shop builds. This
  rarely flags amber here; it does flag if someone tries to schedule
  a solid-surface countertop assembly at SB-ASSY (wrong station type
  — should be `countertop`).
- **Parallel jobs** (`x_sbk_allows_parallel_jobs = True`) — confirms
  you can be on the same MO as a partner. The system tracks each
  assembler's contribution to the work order duration separately.
- **Required skills** (`x_sbk_required_skill_ids` on `mrp.workcenter`)
  — reuses Odoo's `hr.skill`. If a complex carcass (corner unit,
  appliance garage) calls for a specific skill, the planner only
  routes it to assemblers whose `hr.employee.employee_skill_ids`
  cover it.
- **Bottleneck flag** (`x_sbk_is_bottleneck = True`) — yes, you're a
  bottleneck. Idle time at SB-ASSY shows up on the manager's MI
  dashboard quickly.

## Your daily flow

**1. Start of shift (5 min):**

- Open **Kitchen Ops → Workcenters → Carcass Assembly (SB-ASSY)**.
- Glance at *Today's queue* — count the MOs. A normal day is 5–8
  carcasses per assembler, double that for the bay when both
  benches are running.
- Check the **hardware-kit ready** flag on the first 2 work orders.
  The SB-HW operator marks the kit ready when it's on the cart; if
  it's not, you can't start the carcass. If the flag is amber, walk
  to SB-HW and check the cart — the kit may be physically there but
  the operator forgot to tap Done.
- Read the **cabinet code** + **kitchen project** on the first MO
  (lesson 1.7 explains the cut spec the engineer authored). A base
  1-door is a 15-minute job; a tall pantry with internal drawers
  is closer to 45.

**2. Per carcass (the loop):**

For each row in *Today's queue*:

- Tap the row → opens the **Work Order** detail. The panel list shows
  every banded panel that should be at your bench; tick each one off
  against the physical cart.
- If a partner assembler will work the same MO, both of you tap
  **Start**. The work order goes to `progress`. The system records
  two `mrp.workorder.duration` rows, one per `user_id`.
- Square the panels on the assembly jig. Apply glue at the dowel +
  cam-lock joints — the cut spec calls out which joints are
  glued and which are screw-only.
- Drive dowels / cam locks per the assembly drawing. Hand-screw the
  back panel (the rabbet depth comes from the cut spec — see lesson
  1.7).
- Check squareness with the diagonal-measure tape. If the carcass is
  out of square by more than the `shelf_tol` value in the cut spec,
  loosen and re-square; do **not** sand-fit it square later.
- Tap **Done**. The system records actual cycle time. If you and your
  partner are both on the WO, you both tap Done; the system stitches
  your durations together.
- Push the carcass to the SAND cart. Sanding (lesson 1.5) picks it
  up next.

**3. Door hanging (SB-DOOR rotation):**

When you rotate to SB-DOOR:

- The screen looks the same but station type is `assembly` and
  `x_sbk_is_bottleneck = False` — relief. Idle minutes here aren't
  P0.
- The planner's `x_sbk_planning_notes` on SB-DOOR explain why:
  door hanging is split from the carcass bay so the door / paint
  branch can converge here without blocking carcass throughput.
- Doors arrive from PAINT + CURE (lesson 1.5) on a separate cart.
  Match them to the carcass by `cabinet_code` on the MO.

**4. End of shift (5 min):**

- Check *Today's queue* — any WOs still open?
  - **Open and partially done** — tap the row, set the **completed
    carcass count** so the next-shift assembler picks up where you
    stopped.
  - **Open and not started** — leave it; the planner rolls it
    forward.
- If a panel was damaged at CNC + you scrapped a carcass, log it as
  a scrap event on the Done flow.
- If the carcass jig broke, log it as **downtime** (lesson 1.6) with
  reason `tool_change` or `machine_breakdown` before clocking out.

## Common mistakes + how to recover

**"My partner and I both tapped Start, but the system is showing the WO
as `progress` only under my name."**

You're fine. The work order's `state` is a single field — `progress` —
and only flips once when the first Start lands. What's different is
the `mrp.workorder.duration` table: there should be two rows now, one
per `user_id`. Check the *Time Tracking* tab on the WO; if you only
see your row, your partner's tap didn't register. Have them tap Start
again — duplicate start taps within the same minute are deduped.

**"The hardware kit is at my bench but parts are missing — there's no
hinge package for one of the doors."**

Don't start. Walk to SB-HW. The operator marked the kit ready in the
system but didn't verify the count physically. Either the missing part
is back at the crib, or it never got picked. The SB-HW operator can
re-open the kit, mark it incomplete, and have the maintenance
technician escalate. Meanwhile your WO stays in *pending* and the
next MO in your queue is fine to start.

**"I assembled the carcass and it's 4mm out of square."**

Stop. The cut spec's `shelf_tol` is 1.5mm — 4mm is far beyond it.
Disassemble enough to reseat the back panel; the rabbet capture is
usually what's binding. If the cut spec is wrong (the panels physically
don't square up no matter how you seat them), tap *Block* on the WO and
the system raises a `cut_spec_audit` recommendation for the PLM engineer.
The engineer reviews and may raise an ECO against `southbrook.cut.spec`.

**"I tapped Done on the wrong row."**

Open the work order, tap *Undo Done* — available for 10 minutes.
After that, the work order is in `done` state and you have to
manually set the WO back to `progress` (supervisor-only). The MI
engine treats a Done-then-Undone WO as misclick and excludes it
from cycle-time stats so your numbers stay clean.

**"The kitchen_project_id on my MO has been flipped from
`in_production` back to `approved` — the WO disappeared from my queue
mid-shift."**

That means ENG01 (Design Review) revoked the production release on
your kitchen project, probably because the engineer caught a problem
with the cut spec. The MO is paused upstream; your WO is automatically
removed from your queue. Don't try to keep building — flag it to your
supervisor and move to the next MO. The project will reappear in your
queue when ENG01 re-releases.

## What the system is doing behind the scenes

(Optional reading — the database trail of your taps.)

When you tap Start on a parallel-assembled WO, here's what happens:

- **`mrp.workorder`** — `state` flips from `pending` to `progress`
  on the first Start tap. Subsequent Start taps from other users
  are recorded but don't re-flip the state.
- **`mrp.workorder.duration`** — one row per operator session.
  `user_id` is you, `time_start` is now, `time_stop` is null until
  Done. With parallel assembly, two rows track in parallel.
- **`mrp.production`** — the parent MO. Its
  `x_sbk_kitchen_project_id` (from `southbrook_kitchen_workspace`'s
  `sb.kitchen.project` model) tells the MI engine which kitchen
  this carcass belongs to. The `cabinet_code` + `kitchen_room` on
  the production record drive the traveler labels.

The `x_sbk_allows_parallel_jobs = True` setting on SB-ASSY is what
makes the planner schedule a single MO across two assemblers
instead of treating SB-ASSY as a queue of length 1. The setting
is configuration, applied at install in
`southbrook_mrp_kitchen_workcenters/data/mrp_workcenter_seed.xml`.

The downstream handoff: when you tap Done at SB-ASSY, the next
operation in the routing (sanding at SAND) becomes eligible. The
sander's queue refreshes within a minute. Your output is their
input; there's no separate "release" step.

## Quiz (5 questions, applied)

**1.** A complex corner cabinet shows up in your queue. The
`x_sbk_required_skill_ids` on SB-ASSY includes "Corner Carcass
Assembly" but the field is empty on your `hr.employee` record. What
happens, and what should you do?

> The scheduler is permissive — it routed the MO to SB-ASSY even
> though you don't carry the skill, because the matching is hr-side,
> not work-order-side, in v19 CE. You should not start the WO —
> escalate to your supervisor. The supervisor can either ask the
> trained assembler to take the row, or have HR add the skill to
> your `employee_skill_ids` after a quick certification.

**2.** You and a partner are running parallel on the same MO. Your
partner gets pulled to SB-DOOR mid-carcass. What do you tap, and
what happens to their duration row?

> Your partner should tap *Done* on their session before walking
> away — that closes their `mrp.workorder.duration` row with a
> `time_stop` now, and their contribution to the WO is captured.
> You keep going solo; your row stays open until you finish. If
> they forget, their row hangs open and the MI engine flags an
> unclosed duration as a data-quality issue on tomorrow's report.

**3.** The hardware kit for an MO arrives at your bench but the kit
flag is still amber (not ready) on your screen. You can see the
parts physically. What's the right move?

> Don't start — the readiness gate isn't just decoration. Walk to
> SB-HW and ask the hardware operator to mark the kit Done. They
> tap Done on their WO and your screen refreshes within a minute.
> If you start anyway, the MO's hardware step shows as still in
> progress while you're working downstream, which corrupts the
> MO's flow time on the MI report.

**4.** You finish a carcass at 14:32, push it to sanding, and at
14:45 the sander says it's 2mm out of square along the diagonal.
You tapped Done at 14:32. What do you do?

> Tap *Undo Done* on the WO — it's been less than 10 minutes since
> Done. The WO flips back to `progress`. Pull the carcass back from
> the SAND cart, fix the squareness, then tap Done again. The MI
> engine accepts the Done-Undo-Done cycle as a quality recovery and
> doesn't penalise your cycle-time stat. If you were past the
> 10-minute window, you'd need supervisor help to flip the state
> back.

**5.** Your supervisor says SB-ASSY ran at 91% OEE yesterday — above
the 0.85 target. You feel like you were idle a lot. What's the most
likely explanation?

> Two things compound to inflate OEE: (a) parallel-jobs counted as
> two assemblers busy on one WO doubles the "available time
> productive" number; (b) you and your partner closed your duration
> rows promptly. OEE = available time / good output, so when you
> close cleanly with no unlogged idle gaps, the math rewards you.
> Idle for a coffee + bathroom break that takes <5 minutes doesn't
> register; longer idle does. So the supervisor's number is real.

---

## What this lesson does NOT cover

- Native Odoo work-order vocabulary and MRP basics — Odoo's own
  training portal.
- Edge banding (your upstream) — lesson 1.2.
- CNC routing (your upstream's upstream) — lesson 1.3.
- Sanding + finishing (your downstream) — lesson 1.5.
- Downtime logging in detail — lesson 1.6.
- Reading a PLM cut spec for assembly fields (rabbet, dowel spacing,
  joinery) — lesson 1.7.
- The kitchen project release gate that ENG01 runs — Course 2,
  lesson 2.2.
