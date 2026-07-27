---
course: 11 — Creating a New Product End-to-End
chapter: 11.7
title: First MO — The Test Run on the Shop Floor
duration: 40 minutes
audience: Production planner + production manager + lead operator on the new SKU's first manufacturing order; everybody downstream is invited to watch
prereqs: Lesson 11.6 (pricing signed off), Lesson 11.4 (BoM with operations), Lesson 11.5 (configurator wired), Lesson 2.1 (kitchen projects vs sale orders), Lesson 2.2 (the approved→in-production release gate / ENG01), Lesson 2.3 (bottleneck-aware scheduling), Lesson 1.1 + the per-station lessons 1.2–1.5, Course 3 (MI dashboards — Manufacturing Intelligence — for the post-run debrief)
custom_modules: southbrook_kitchen_workspace, southbrook_kitchen_mrp, southbrook_mrp_pm, southbrook_mrp_kitchen_workcenters, southbrook_premium_orchestration, southbrook_manufacturing_intelligence
---

# First MO — The Test Run on the Shop Floor

## Who this lesson is for

You're the production planner scheduling the new SKU's first MO,
the production manager supervising the run, and the lead operator
(usually whichever station has the most expected variance —
typically `SB-EDGE` or `SB-CNC-BORE`) handling the hands-on work.
This is the first time the platform touches the new product end-
to-end on real materials. It's also the first time you'll see
actual cycle times vs the estimates you typed into the BoM in
lesson 11.4 — and the variance is *information*, not failure.

This lesson is the workflow for running that first MO with
deliberate eyes on the things that go wrong on first runs (cycle
time variance, scrap, edge-band misses, hardware-resolver
surprises), and how to turn the data into actionable feedback for
the post-run debrief that informs lesson 11.8.

## Where this lives on the site

> **Sales → Kitchen Workspace → Projects → New**

…to create the kitchen project that wraps the test order. Then:

> **Sales → Orders → Order Builder**

…to create the sale order against an internal customer (a
sandboxed `res.partner` named *Demo — First MO* is the convention).
Once confirmed:

> **Kitchen Ops → Production Release Queue**

…where the planner + ENG01 engineer walk the release gate (lesson
2.2).

> **Manufacturing → Operations → Manufacturing Orders → \<the MO\>**

…to monitor the MO state through `confirmed → in_progress → done`.

> **Kitchen Ops → Shop Floor → \<each workcenter\>**

…where the operators see their work orders for the run.

Post-run:

> **Kitchen Ops → MI Dashboards**

…for the cycle-time variance, scrap, and downtime data.

## What your screen shows

The `sb.kitchen.project` form
(`/Users/naadmin/southbrook-v19cr/addons/southbrook_kitchen_workspace/models/sb_kitchen_project.py:43`):

- **Code** (`code`) — convention for the first MO: `<sku_xml_id>-T1`
  (e.g. `wall_3dr_corner-T1` for the first test). T2/T3 follow if
  needed.
- **State** (`state`) — `draft → designing → awaiting_customer
  → approved → in_production → done → cancelled`. For a test run
  you skip `awaiting_customer` (no customer to wait on; the test is
  internal).
- **Partner** (`partner_id`) — the internal sandbox partner
  *Demo — First MO*.
- **Salesperson** (`salesperson_id`) — you.
- **Sale order** (`sale_order_id`) — the linked sale order
  with the new SKU as a single line.

The `mrp.production` form (standard Odoo MO):

- **Product** — the configured variant of the new SKU.
- **BoM** — the new BoM from lesson 11.4 (version 1).
- **Operations** — every routing operation, becomes a
  `mrp.workorder` with `state pending → progress → done`.
- **Components** — every BoM line becomes a `stock.move`.

The Production Release Queue (lesson 2.2 — `project.task`):

- **`southbrook_release_cad_approved`** — boolean.
- **`_cutlist_approved`** — boolean.
- **`_bom_verified`** — boolean.
- **`_crew_reserved`** — boolean.
- **`_equipment_available`** — boolean.
- **`southbrook_production_release_state`** — overall computed
  state (`blocked / pending / ready / released`).

The Shop Floor view per workcenter (lesson 1.2 / 1.3 / 1.4 / 1.5):

- **Today's queue** — work orders ordered by planner sequence.
- **Current operation** — what the operator is on right now.
- **Cycle time** — the planned time vs the actual time
  (`mrp.workorder.duration` durations).

## Your daily flow

**1. Pre-flight (10 min — the night before):**

- Confirm the new SKU is *active for sale*.
- Confirm at least one variant exists (the test session in lesson
  11.5 left one).
- Confirm `standard_price` on the template is sane.
- Talk to the production manager: schedule a 1-hour pre-shift
  walk-through on the morning of the test, with the lead operator
  attending. The walk-through covers: *here's a new SKU, here's
  what's different about it, here's where I expect variance, here
  are the things you should write down*.

**2. Create the kitchen project (5 min):**

- **Sales → Kitchen Workspace → Projects → New**.
- **Code**: `<xml_id>-T1`.
- **Partner**: *Demo — First MO*.
- **Theme**: free text, e.g. *"First MO test — Wall 3-Door
  Corner"*.
- **State**: starts `draft`. Save.
- *Action → Move to Designing → Approved* (you skip
  `awaiting_customer` for an internal test). The
  `action_set_state()` method
  (`sb_kitchen_project.py:114`) enforces the
  `VALID_TRANSITIONS` graph (line 28); the `draft → designing →
  approved` path is legal.

**3. Create the sale order (10 min):**

- **Sales → Orders → Order Builder → New**.
- **Customer**: *Demo — First MO* (resolves to whatever channel
  you've assigned — typically `retail` for internal tests).
- **Kitchen project**: link to the project you just created.
- **Add a line**: pick your new template, click *Configure*, pick
  the **canonical baseline configuration** (no premium upgrades
  — the test should run the most representative version of the
  product, not a corner case).
- *Save*.
- *Confirm* the sale order. State flips `draft → sale`.

**4. Walk the release gate (15 min):**

The release gate (lesson 2.2) is two-person: the planner verifies
the data-side flags, then the ENG01 engineer verifies the
engineering-side flags. The MO **cannot release** until all five
booleans are `True`.

- **Kitchen Ops → Production Release Queue**. Find the task that
  spawned from your sale order.
- **Planner-side**:
  - `_crew_reserved` — confirm operators are available for the
    expected MO run window. Tick on if so.
  - `_equipment_available` — confirm workcenters needed
    (`SB-SAW`, `SB-EDGE`, `SB-CNC-BORE`, `SB-ASSY`, `SB-DOOR`,
    `SAND`/`PAINT`/`CURE` if finished, `SB-HW`, `SB-QC`,
    `SB-PACK`) aren't all booked solid. Tick on.
- **ENG01-side** (the ENG01 engineer with `code=ENG01` workcenter
  membership):
  - `southbrook_release_cad_approved` — confirm the FreeCAD
    render (lesson 4.3) for this product matches expectation, or
    that the cabinet doesn't need CAD (rare). Tick on.
  - `_cutlist_approved` — confirm the cut list preview (lesson
    11.4 step 8) is sensible. Tick on.
  - `_bom_verified` — confirm the BoM components and operations
    are present and the auto-resolved hardware lines (lesson
    5.3) look right. Tick on.
- Once all five are on,
  `southbrook_production_release_state` computes to `released`.
- The MO is now eligible for shop-floor scheduling.

**5. Hand-off to the operators (5 min):**

- Print or display the **Signature Spec Sheet** (the customer-
  facing PDF) **and** the *Shop Copy* + *Cut Spec* per cabinet.
  Even though the customer doesn't see the spec sheet for an
  internal test, the operators benefit from seeing the same view
  the customer would see.
- Brief the lead operator: *"This is the first run of
  `<sku_xml_id>`. Cycle times in the BoM are estimates from PLM;
  measure what actually happens and don't be shy about writing
  down deviations."*

**6. Run the MO (varies — typically 2-4 hours for a single
cabinet):**

The lead operator runs the operations in sequence (or in parallel
where the routing allows). Per-station behaviour is covered in
lessons 1.2 through 1.5 — what's specific to a *first MO* is:

- **Watch cycle time variance.** Actual cycle time vs planned
  (the `time_cycle_manual` you set in lesson 11.4). The MI engine
  will flag `slow_workorder` overnight if actual > planned × 1.2.
  *Don't pre-empt this*; let the data land. Variance on a first
  run is the **point** — you're calibrating estimates.
- **Watch scrap.** Edge-band misses, panel chips at the saw,
  hardware that doesn't fit. Each scrap event is logged via the
  operator's *scrap reason* on Done (lesson 1.2). Each scrap
  event fires a `scrap_event` recommendation overnight (for the
  production manager) and a `cut_spec_audit` recommendation (for
  the PLM engineer). On a first MO, expect at least one scrap
  event — and welcome it.
- **Watch edge-band misses specifically.** The `SB-EDGE` station
  is the most common source of first-MO issues — new SKUs often
  have edges that need banding in an order the operator wouldn't
  guess. The operator at `SB-EDGE` should walk through their
  decision: *"I banded these four edges; is that right?"* Sign
  off before the panel moves downstream.
- **Watch the hardware auto-resolver output.** When the MO
  confirms, `southbrook.hardware.catalog.resolve(...)` runs
  (lesson 5.3) and auto-creates hardware lines based on door
  count, shelf count, etc. *Confirm the resolved hardware lines
  match what the BoM author expected.* Misses here mean the BoM
  was wrong, the hardware-map JSON
  (`southbrook_hardware_catalog/data/hardware_map.json`) doesn't
  know about the new SKU's family, or the auto-resolver's
  classification logic mismatched.

**7. End-of-run wrap-up (15 min):**

- Mark the last `mrp.workorder` *Done*. The MO transitions to
  `done`. The `sale.order` line gets the *delivered* quantity.
- The kitchen project's state can move
  `in_production → done` via
  `sb_kitchen_project.action_set_state('done')`.
- Walk every operator's *Done* button entry: any *misclick*
  notes? Any *scrap reason* not captured? Any *blocked* work
  orders that need addressing?

**8. Post-run debrief (next morning, 30 min):**

The morning after the MO completes (overnight crons have run, MI
has computed):

- **Kitchen Ops → MI Dashboards** — read the per-station cycle
  time variance for the new SKU's MO. Outlier stations are your
  priorities for the lesson 11.8 ECO.
- **Hermes Console → Recommendations queue** — read the
  recommendations the MI engine filed overnight:
  - `slow_workorder` — actual cycle time > planned × 1.2.
  - `scrap_event` — scrap was logged.
  - `cut_spec_audit` — PLM engineer should review (the cut spec
    constants might not be right for this SKU).
  - `materials_blocked` — a work order was blocked.
- **Operators' notebooks** — collect the lead operator's notes.
  Verbal feedback beats system data here.
- Document everything in the conception folder under a new
  file `first_mo_debrief.md`. This is the input to lesson 11.8
  (production release + iteration) — the formal ECO that
  capitalises the learnings into the BoM and routing.

## Common mistakes + how to recover

**"The MO confirmed but the work orders didn't show up on the
shop-floor view."**

The release gate (lesson 2.2) wasn't fully closed —
`southbrook_production_release_state` is still `blocked` or
`pending`. Operators see no queue until `released`. **Recovery**:
re-check all five booleans on the project task; the failing one
shows in `southbrook_production_release_reason`.

**"The hardware auto-resolver added zero hardware lines."**

Two likely causes: (a) `southbrook.hardware.catalog.resolve(...)`
doesn't know about the new SKU's family — the
`hardware_map.json` (`data/hardware_map.json` in
`southbrook_hardware_catalog`) keys off attribute values like
`per_door`, `per_door_soft_close`, `per_shelf`, `per_cabinet`,
`per_family`. Check the new SKU's family is mapped. (b) The
resolver's classification of the new variant is wrong — the
variant doesn't carry a recognisable family attribute. **Recovery
during the MO**: add hardware lines manually for this MO; **after
the MO**: file an ECO (lesson 11.8) to update
`hardware_map.json` to recognise the new family.

**"The first MO's cycle time at `SB-EDGE` was 45 minutes; planned
was 12."**

Three causes to consider: (a) genuine first-run learning curve —
the operator hadn't seen this SKU before; expect this to drop on
the second run. Don't act on this. (b) The BoM cycle-time estimate
was wrong — measure 2-3 more runs before deciding. (c) The cabinet
genuinely has more banded edges than the BoM accounted for — fix
in the BoM in lesson 11.8 ECO. **Do not** edit the BoM directly
during the first run — capture in the debrief and let ECO process
catch it.

**"The cut list preview at MO confirm time showed panel dimensions
that don't match the conception sketch."**

The cut spec's NF14 constants may not be right for this SKU
(lesson 11.3's path-b decision is showing up). **Recovery**: pause
the MO at the planner level (don't release yet). Re-read lesson
11.3 — does this product genuinely need per-product BoM overrides
the BoM author didn't add? Add them via a quick ECO before the MO
runs. Better to delay a day than cut wrong panels.

**"The MO completed but the kitchen project is stuck in
`in_production`."**

The project doesn't auto-transition to `done` — manual click is
required via `action_set_state('done')`. (Lesson 2.1 covers the
state machine.) **Recovery**: open the kitchen project, click the
*Mark Done* button.

**"The MI engine fired a `slow_workorder` recommendation but the
cycle was fine — it's reading the changeover time as run time."**

The operator forgot to tap *Changeover* between work orders at
`SB-EDGE` (lesson 1.2). The system attributed the changeover time
to the next work order's cycle. **Recovery**: the recommendation
is wrong; mark it *invalid reason: unlogged changeover* on the
Hermes Console. Coach the operator to tap *Changeover* on the
next run. Not a BoM issue.

## What the system is doing behind the scenes

When the sale order confirms (`action_confirm`):

- The standard `sale.order.action_confirm` runs.
- `southbrook_kitchen_mrp` extensions create the `sb.cutlist`
  (`sb_cutlist.py:70`) linked to the MO via `mo_id`. State
  `draft`.
- `southbrook.hardware.catalog.resolve(...)` runs to add
  hardware lines to the BoM rollup for this MO (lesson 5.3).
- The `sb.production.package`
  (`sb_production_package.py:26`) bundles `mo_id`,
  `cutlist_id`, `hardware_package_id` — the holistic "what we're
  going to build" record.
- The `southbrook_freecad_bridge` (lesson 4.3) fires
  `_post_cad_render_job` if `freecad_bridge.enabled` system
  parameter is true.

When the release gate clears:

- `southbrook_production_release_state` recomputes
  (`southbrook_premium_orchestration/models/project_task.py:134`)
  to `released`. The `action_send_to_production()` method
  (`southbrook_mrp_pm/models/sale_order.py:172`) is callable.
- The MI engine cron `_cron_refire_gates` re-evaluates every 15
  minutes; the planner can also force a re-eval.

When each work order completes:

- `mrp.workorder.duration` rows accumulate
  `time_start`/`time_stop`/`loss_id`.
- The MI engine reads these overnight (Course 3) to compute
  per-station OEE and cycle time variance.

When the overnight crons run:

- The MI engine's `_evaluate_workorder_variance` job (or
  similar) computes
  `actual_cycle / planned_cycle` per work order. > 1.2 fires
  `slow_workorder`.
- Scrap-logged work orders fire `scrap_event` for the
  production manager and `cut_spec_audit` for the PLM engineer.
- All recommendations land in `hermes.recommendation` (or the
  equivalent — Course 3) for the production manager's morning
  triage.

The bridge addon `southbrook_plm_productgraph` does **not** fire
on the first MO — it only fires on `southbrook.eco.action_apply()`
where the ECO targets a BoM (creates a `pg.release`). The first MO
produces *data*, which informs the lesson-11.8 ECO; the ECO
fires the bridge.

## Quiz (5 questions, applied)

**1.** You scheduled the first MO and the release gate has `_bom_
verified = False`. The ENG01 engineer says *"I haven't reviewed
the BoM yet — give me an hour."* What do you do?

> Wait the hour. Do **not** flip the boolean yourself, even though
> you have the technical access. The release gate is a two-
> person handoff specifically to prevent first MOs from running
> against unreviewed BoMs. The cost of waiting one hour is small;
> the cost of running a wrong BoM on real materials is large.

**2.** The first MO is mid-run. The operator at `SB-EDGE` says the
cycle is taking three times the planned time and asks whether to
pause. What do you say?

> Don't pause. Let the run complete on this cabinet and capture
> the actual cycle time. A first MO is a measurement; mid-run
> changes contaminate the data. Note the operator's observation in
> the debrief notebook ("3x planned cycle, possibly because: ..."),
> finish the run, then decide in lesson 11.8 whether the BoM
> cycle time needs revising or the operator needs more training
> on the new SKU.

**3.** The MO completes. The MI dashboard shows the OEE at
`SB-EDGE` was 47% during the run — well below the 78% target.
What do you do?

> Two questions: (a) was 47% a one-cabinet artefact (low-volume
> MOs inflate setup-time-as-percentage and depress OEE
> artificially)? Almost certainly yes for a single-cabinet test
> MO. The OEE number is real but not actionable. (b) Did the
> operator log changeovers correctly? Check the work order
> durations for unlogged changeover gaps. If they're there,
> coach. If not, the cycle is what it is and you'll calibrate
> across the next 5-10 MOs.

**4.** The hardware auto-resolver added the wrong soft-close
hinge count — 3 doors got 6 hinges instead of 4. What do you do?

> The auto-resolver's `per_door` or `per_door_soft_close`
> classification mis-counted doors on this SKU (likely because
> the variant's `sb_door_count` field on `sale.order.line`
> (`sale_order_line.py:52`) wasn't populated correctly by the
> configurator). For this MO, edit the hardware lines manually to
> 4 hinges. For lesson 11.8 ECO, file a bug: configurator
> attribute setup (lesson 11.5) needs a fix so `sb_door_count`
> populates right for this SKU's variants.

**5.** The MO is complete and the kitchen project is `done`. The
production manager asks *"are we ready to release the SKU to
real customer orders?"* What's the right answer?

> Not yet — one MO is sample-size-one. The recommended path:
> (a) gather the first-MO debrief (this lesson, step 8); (b)
> raise the lesson-11.8 ECO with the learnings (cycle time
> revisions, scrap-cause fixes, hardware-map updates); (c) apply
> the ECO; (d) run **one more** test MO with the revised BoM. If
> the second test is clean, *then* release the SKU. Two clean
> tests gives you confidence to charge a customer for it.

---

## What this lesson does NOT cover

- Native Odoo MO state machine, work order vocabulary, scrap
  workflow — Odoo's own MRP training.
- Kitchen project state machine — lesson 2.1.
- The release gate booleans in detail — lesson 2.2.
- Per-station operator workflows — lessons 1.2 through 1.5.
- The hardware auto-resolver internals — lesson 5.3.
- The FreeCAD bridge — lesson 4.3.
- MI dashboards in detail — Course 3.
- Hermes Console recommendation triage — Course 3 lessons 3.2 +
  3.3 (and the customer-service perspective in lesson 6.3).
- The post-MO ECO that capitalises learnings — lesson 11.8.
- Releasing the SKU formally to customers — lesson 11.8.
