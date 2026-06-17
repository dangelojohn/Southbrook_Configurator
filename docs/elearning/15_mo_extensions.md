---
course: 15 — Manufacturing Module Deep Dive
chapter: 15.2
title: Manufacturing Order Extensions — Every Field Southbrook Adds to mrp.production
duration: 30 minutes
audience: Production Manager + Production Planner reading the MO form daily
prereqs: Lesson 15.1, Course 2 lesson 2.1 (kitchen projects), Course 3 lesson 3.1 (MI dashboards), comfortable with native Odoo MO state machine
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_kitchen_tools, southbrook_manufacturing_intelligence
---

# Manufacturing Order Extensions — Every Field Southbrook Adds to mrp.production

## Who this lesson is for

You spend half your day in front of a Manufacturing Order. The native
Odoo MO form is the spine; Southbrook stitches in two notebook pages
(Kitchen + Intelligence), nine `x_sbk_*` fields, eight `x_mi_*`
fields, three `southbrook_tool_*` fields, and a fistful of computes.
This lesson walks you through every one — what writes it, when it
changes, and what to do when it shows the wrong value. Read this
before you ask a developer "what's this field?"

## Where this lives on the site

> **/odoo/manufacturing → Manufacturing Orders → <MO number>**

Or use the Southbrook PM shortcuts:

> **Southbrook PM → Ready Queue** — confirmed + progress MOs grouped by state
> **Southbrook PM → In Production** — state=progress only
> **Southbrook PM → Late Orders** — `date_deadline < now`, not done/cancel

All three open the same `mrp.production` form. The form has the
native sheet on top, then a notebook with: **Components** (native),
**Work Orders** (native), **Miscellaneous** (native), **Kitchen**
(Southbrook), **Intelligence** (Southbrook), then any further native
tabs.

## What your screen shows — the Kitchen notebook

Added by `southbrook_mrp_kitchen_workcenters` via
`view_mrp_production_form_sbk_kitchen`. Two groups inside:

**Project Linkage group:**

| Label | Field (model.field, owner) | Type | What it carries |
|---|---|---|---|
| Kitchen Project | `x_sbk_kitchen_project_id` (`mrp.production`, kitchen_workcenters) | M2O → `sb.kitchen.project` | The customer's kitchen this MO is producing for. Tracked; indexed. |
| Room / Zone | `x_sbk_kitchen_room` (`mrp.production`, kitchen_workcenters) | Char | Free-text room label (e.g. "Master Kitchen — Run A"). Tracked. |
| Cabinet Code | `x_sbk_cabinet_code` (`mrp.production`, kitchen_workcenters) | Char | Customer-facing cabinet identifier (e.g. "B30", "W2430"). Tracked. |
| Install Due Date | `x_sbk_install_due_date` (`mrp.production`, kitchen_workcenters) | Date | When the customer expects the install. DISTINCT from native `date_planned_start`/`date_deadline`. Tracked. |
| Priority Level | `x_sbk_priority_level` (`mrp.production`, kitchen_workcenters) | Selection: urgent / high / **normal** / low | Shop-floor sort. Distinct from native `priority` (which Odoo uses for stock reservation). Tracked. |

**Complexity & Totals group:**

| Label | Field (model.field, owner) | Type | What it carries |
|---|---|---|---|
| Complexity Factor | `x_sbk_complexity_factor` (`mrp.production`, kitchen_workcenters) | Float(4,2), default 1.0 | Multiplier fed into the operation-template duration formula. 1.2 = "this MO is 20% harder than baseline." |
| Total Estimated Min | `x_sbk_total_estimated_min` (`mrp.production`, kitchen_workcenters) | Float(10,2), stored compute | Sum of `workorder_ids.x_sbk_kitchen_expected_min` |
| Total Actual Min | `x_sbk_total_actual_min` (`mrp.production`, kitchen_workcenters) | Float(10,2), stored compute | Sum of `workorder_ids.duration` |
| Total Variance Min | `x_sbk_total_variance_min` (`mrp.production`, kitchen_workcenters) | Float(10,2), stored compute | actual − estimated |

Plus a **Recalc All Workorder Durations** button that fires
`action_sbk_recalc_all_workorder_durations` — useful when you've
changed the complexity factor mid-flight and want every WO's
`x_sbk_kitchen_expected_min` re-derived from the operation templates.

## What your screen shows — the Intelligence notebook

Added by `southbrook_manufacturing_intelligence` via
`view_mrp_production_form_mi`. The page is one big group with:

| Label | Field (model.field, owner) | Type | What it carries |
|---|---|---|---|
| MI Status | `x_mi_status` (`mrp.production`, MI) | Selection: **ok** / review / blocked | The badge. Green/amber/red on the form. Driven by aggregate counts below. |
| Blocker Count | `x_mi_blocker_count` (`mrp.production`, MI) | Integer | Number of `southbrook.mi.check` rows with `severity='blocker'`. |
| Warning Count | `x_mi_warning_count` (`mrp.production`, MI) | Integer | Number with `severity='warning'`. |
| Next Action | `x_mi_next_action` (`mrp.production`, MI) | Text | Human-language sentence the engine writes describing the highest-priority blocker. |
| Yield % | `x_mi_yield_pct` (`mrp.production`, MI) | Float | Sheet yield from cutlist nesting. |
| Waste Area m² | `x_mi_waste_area_m2` (`mrp.production`, MI) | Float | Wasted sheet area in m². |
| MI Checks | `x_mi_check_ids` (`mrp.production`, MI) | One2many → `southbrook.mi.check` (inverse `production_id`) | The actual check rows, listed inline. Decorated red/amber/blue by severity. |

Plus a **Recompute Intelligence** button calling
`action_recompute_manufacturing_intelligence()` which delegates to
`southbrook.mi.engine._recompute_production(self)`.

**Not exposed** on the form: `x_mi_bottleneck_workcenter_id` (M2O →
`mrp.workcenter`). The engine declares it but doesn't write it yet —
hidden until the engine path lands.

## What your screen shows — Tool Consumption (smart button)

Added by `southbrook_mrp_kitchen_tools` (no notebook page; smart
button on the form header area when the tools addon is installed):

| Field (model.field, owner) | Type | What it carries |
|---|---|---|
| `southbrook_tool_consumption_ids` (`mrp.production`, tools) | One2many → `southbrook.workorder.tool.consumption` | All tool consumption rows across this MO's workorders, joined via `production_id` related field on the consumption model |
| `southbrook_tool_consumption_count` (`mrp.production`, tools) | Integer compute | Count for smart button |
| `southbrook_tool_consumption_cost` (`mrp.production`, tools) | Float stored compute | Sum of `total_cost` across consumption rows |

The smart button (`action_view_southbrook_tool_consumption`) opens a
list filtered to this MO so you can see every blade-minute, bit-pass,
and consumable spend.

## The list view extensions

`view_mrp_production_tree_sbk_kitchen` adds these columns to the
default MO list:

- Install Due Date (`x_sbk_install_due_date`)
- Kitchen Project (`x_sbk_kitchen_project_id`)
- Cabinet Code (`x_sbk_cabinet_code`)
- Priority Level (`x_sbk_priority_level`)

So when you're at **Southbrook PM → In Production**, you immediately
see which job is for which kitchen, which cabinet, due when, at what
priority. The native MO list doesn't carry any of that.

## Your daily flow

**1. Triage the queue (morning, 10 min):**

- Open **Southbrook PM → Ready Queue**, default-grouped by state.
- The `confirmed` group is what's eligible for release. Look at
  `x_mi_status` — anything with `blocked` shouldn't be released yet;
  click into it and read `x_mi_next_action` for the one-sentence
  reason.
- Look at the `progress` group. `x_mi_status = review` is a yellow
  flag — open the MO, scroll to the Intelligence tab, check the
  warning rows. Often it's "yield below 75%" or "edge bander panel
  size near max" — neither stops production but both need a
  follow-up note to the planner.

**2. Mid-flight diagnostics (the loop):**

- Operator pages: "MO MO/00347 has 12 panels but I only see 11 in
  my queue." Open MO/00347, Kitchen tab, check `x_sbk_kitchen_room`
  and `x_sbk_cabinet_code` — the operator may be looking at the
  wrong MO for the same kitchen. Then jump to the Intelligence tab,
  hit Recompute MI. If the engine writes a new blocker, that's
  your answer.
- Workcenter is idle: open the MO, look at
  `x_sbk_total_estimated_min` vs `x_sbk_total_actual_min`. If
  variance is heavily positive, the operator's running slow; if
  near zero but the MO isn't progressing, there's a tool-readiness
  problem (see lesson 15.3).

**3. End-of-day adjustments (5 min):**

- Anything you change on the MO that affects timing
  (complexity factor, priority level, install due date) — hit the
  Recalc button so the workorder estimates stay consistent.
- If you've shifted an install date, update
  `x_sbk_install_due_date` first, then update the native
  `date_deadline` to match. They're TWO separate fields by design:
  `x_sbk_install_due_date` is the customer's expectation;
  `date_deadline` is what the scheduler uses. Keep them in sync or
  document the gap in the MO's chatter.

## Common mistakes + how to recover

**"I changed `x_sbk_complexity_factor` from 1.0 to 1.3 but the
totals didn't move."**

The MO-level totals are stored computes that aggregate workorder
durations. Workorders have their OWN
`x_sbk_kitchen_expected_min` which doesn't auto-recompute when you
change complexity — it's set at WO creation from the operation
template. Hit **Recalc All Workorder Durations** on the MO. That
fires the operation-template formula again against the new
complexity factor and propagates.

**"`x_mi_status` is `ok` but I can count 2 blocker checks in the
list below."**

Storage drift. The MI engine writes `x_mi_status` and the count
fields synchronously, but if you've manually deleted or re-inserted
check rows (rare; usually only happens during data migration), the
aggregates won't catch up until the next engine pass. Hit
**Recompute Intelligence**. The engine re-aggregates as its last
step.

**"I set `x_sbk_install_due_date` to today, but the MO is still in
`confirmed` and the planner says nothing's changed in their queue."**

The Install Due Date is NOT the scheduler's deadline. The scheduler
reads `date_deadline` (native). Update both. The Install Due Date
field is for the dealer / install crew; the deadline is for the
shop. Decoupling them is by design — sometimes the install is in
two weeks but you want production done in one for slack.

**"The MO has `x_mi_yield_pct = 0` and yield % shouldn't be zero."**

`x_mi_yield_pct` is written by the MI engine ONLY after it sees a
nested cutlist (`sb.cutlist.state = 'nested'`). Before nesting,
this field is 0 by default. Don't read it as "0% yield" — read it
as "not measured yet." When the nest result lands via
`sb.cutlist.from_nesting_result(payload)`, the engine pass fills it
in.

**"I want to filter MOs by which Kitchen Project they belong to but
the native search doesn't expose project."**

The MO list view extension adds the column but the search-filter
inheritance for the Kitchen Project field is **TBD** — currently
you have to type the project name into the global search or use
the kitchen project's smart button to navigate the other way. File
a ticket if this becomes routine.

## What the system is doing behind the scenes

The Kitchen tab fields are plain stored fields on `mrp.production`
with tracking enabled — every change lands in the MO's chatter
automatically, so audit trails are free. The totals
(`x_sbk_total_estimated_min` etc) are stored computes that depend
on `workorder_ids.x_sbk_kitchen_expected_min` and
`workorder_ids.duration`. Saving a workorder kicks the recompute.

The Intelligence tab fields are written by
`southbrook.mi.engine` which lives in
`southbrook_manufacturing_intelligence/models/mi_engine.py`. The
engine:

1. Iterates `southbrook.mi.check` definitions (the check catalog).
2. For each check, runs its match function against the MO + linked
   `sb.production.package` (if present).
3. For each match, inserts a `southbrook.mi.check` row with
   `production_id = self.id`, `severity`, `category`, and a
   `next_action` string.
4. Aggregates: `x_mi_blocker_count = count(severity='blocker')`,
   `x_mi_warning_count = count(severity='warning')`,
   `x_mi_status = 'blocked' if blockers else 'review' if warnings
   else 'ok'`.
5. Writes the highest-priority blocker's `next_action` to the MO's
   `x_mi_next_action`.

The engine is **idempotent** — it deletes all `southbrook.mi.check`
rows for the MO before re-inserting. Don't manually edit check rows;
they're computed state.

The tool consumption smart button reads
`southbrook.workorder.tool.consumption` filtered by the MO's
workorders (via the consumption model's `production_id` related
field). The total cost is rolled up nightly so the smart button is
always cheap to render.

## Fields that DON'T exist (TBDs and product gaps)

The brief and several older docs reference these — they are NOT in
v19 code as of writing. If you see them in a screenshot or a stale
doc, ignore:

| Referenced as | Actually exists? | Real story |
|---|---|---|
| `x_southbrook_sale_order_id` (SO linkage on MO) | **No** | MO → SO linkage is via `x_sbk_kitchen_project_id → sb.kitchen.project` → SO. There's no direct FK from MO to SO. |
| `southbrook_production_release_state` | **No** | The release gate state machine lives on `sale.order.production_approval_state` (added by `southbrook_mrp_pm`), not on the MO. |
| `southbrook_install_readiness_state` | **No** | Install readiness is implied by `sb.production.package.state` (`draft / ready / released / done`), not a separate field on the MO. |
| Cut spec snapshot fields on MO | **No** | The cut spec is referenced live via the BoM's `_get_cut_constants` seam (lesson 15.4). The MO carries no frozen snapshot. (Course 8 flagged this as a real gap; the design intent is "PLM is the source of truth, the MO follows.") |
| Project task linkage on MO | **No** | The MO links to a `sb.kitchen.project`, which has its own `project.task` structure. No direct `task_id` on the MO. |
| `x_mi_edge_band_m` on MO | **No** | This field lives on `sb.production.package` (lesson 15.7), not on the MO. |

If any of these become real (filed tickets), this lesson updates.

## Quiz (5 questions, applied)

**1.** You change `x_sbk_priority_level` from `normal` to `urgent`
on an MO that's already `progress`. The operator's shop floor
queue doesn't re-sort. Why?

> The shop floor view sorts on the WORKORDER queue, not the MO
> queue. Changing the MO's priority writes the field and tracks
> the change, but the workorders inherit their sort key from
> `mrp.workorder.date_planned_start`, not from the MO. To bump
> the workorders, the planner has to re-plan the MO (which moves
> workorder start times). Updating the priority is informational
> for managers; it does NOT physically re-order the floor.

**2.** You're triaging an MO whose `x_mi_status = blocked` and
`x_mi_next_action` says "Edge band length exceeds workcenter
capacity at SB-EDGE." What's the actual cause and where do you
look?

> The MI engine ran the "edge band capacity" check. It compared
> the cutlist's total edge meters against SB-EDGE's hourly
> throughput against the install due date. Look at the Intelligence
> tab's `x_mi_check_ids` list — the specific check row will give
> you the calculated capacity headroom. The fix is on the planner
> side: either push the install date or split the MO across two
> days at SB-EDGE.

**3.** A developer says "I'm adding a custom field to track which
shipping container an MO will go on. What's the right field name
prefix?"

> Use `x_southbrook_*` if the field is platform-wide, `x_sbk_*` if
> it's tied to the kitchen workcenter logic, `x_mi_*` only if
> written by the MI engine. For shipping container tracking,
> `x_southbrook_shipping_container_id` is appropriate. Avoid bare
> field names — the prefix is what lets future devs trace ownership.

**4.** Your sysadmin shows you a screenshot from 2026-04 of an MO
with a "Production Release State" field. The current MO form
doesn't show it. What happened?

> The April brief proposed `southbrook_production_release_state`
> on `mrp.production` as part of the release gate. In execution,
> the release gate landed on `sale.order` instead
> (`production_approval_state` field, added by `southbrook_mrp_pm`).
> The MO doesn't carry a separate release state; "the MO exists"
> IS the release. The old screenshot was a draft.

**5.** The Total Variance Min on an MO is +245 minutes (actual >
estimated). Which addon's logic do you patch to dig in?

> The variance field is owned by `southbrook_mrp_kitchen_workcenters`
> (`x_sbk_total_variance_min`, stored compute). But the underlying
> per-workorder fields (`x_sbk_kitchen_expected_min` and
> `duration`) come from `mrp.workorder` and the operation-template
> formula in `southbrook.kitchen.operation.template`. Patch the
> template's `compute_expected_duration` if the estimates are
> systematically low; don't override the variance compute itself.

---

## What this lesson does NOT cover

- The workorder side (variance, tool readiness, downtime) → lesson 15.3.
- The cut-spec seam in the BoM that drives panel math → lesson 15.4.
- Workcenter form + alternative chain → lesson 15.5.
- MO view customization (Kanban, search filters) → lesson 15.6.
- MO ↔ cutlist ↔ hardware ↔ production package linkage → lesson 15.7.
- The actual MI engine check catalog (what rules fire when) → Course 3 lesson 3.1.
- The native MO state machine (`draft → confirmed → progress → done`) → Odoo native training.
