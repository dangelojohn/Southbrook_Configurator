---
course: 15 — Manufacturing Module Deep Dive
chapter: 15.3
title: Work Order Extensions — Tool Readiness, Variance, Downtime
duration: 30 minutes
audience: Operator + Planner + Production Manager working the WO surface
prereqs: Lesson 15.1, Lesson 15.2, Course 1 lessons 1.2-1.5 (operator role lessons), Course 1 lesson 1.6 (downtime), comfortable with native Odoo WO state machine
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_kitchen_tools
---

# Work Order Extensions — Tool Readiness, Variance, Downtime

## Who this lesson is for

You're at the keyboard or the touchscreen and you tap **Start** on a
work order. Behind that one tap, three Southbrook systems engage:
the **tool readiness gate** decides whether your machine can even
proceed, the **variance compute** starts comparing your real time
against the operation template's prediction, and any pause/resume
gets stitched into the **downtime ledger**. This lesson is the field
guide to all of it — every custom field on `mrp.workorder`, the
state machines they drive, and how to read them when something's
wrong.

## Where this lives on the site

> **Manufacturing → Operations → Work Orders** — native list, opens the WO form
> **Manufacturing → Operations → Southbrook Kitchen → Work Center Downtime** — the downtime ledger
> **/my/southbrook/floor** — Floor Manager portal (tablet view, separate from Odoo backend)

On the WO form, the Southbrook stack adds:

- A **Tool Readiness** statusbar widget at the top of the header
  (added by `southbrook_mrp_kitchen_tools`).
- A **Southbrook Tool Readiness** group in the sheet (shown only
  when the state isn't `not_checked`).
- A **Check Tool Readiness** button in the header.
- A handful of Southbrook fields surfaced inline (variance,
  cost-estimate, expected-min) by the
  `southbrook_mrp_kitchen_workcenters` addon.

Note: the form view inheritance hits
`mrp.mrp_production_workorder_form_view_inherit` — the **planner-side
backend form**, NOT the shop-floor touchscreen view. The shop-floor
view (the big-button OWL component) reads the same fields but renders
its own UI. Operators see tool readiness on both surfaces; planners
get the full field set on the backend.

## What your screen shows — fields on mrp.workorder

### Owned by `southbrook_mrp_kitchen_workcenters`

| Label | Field (model.field, owner) | Type | Computed from |
|---|---|---|---|
| Kitchen Expected Min | `x_sbk_kitchen_expected_min` (`mrp.workorder`, kitchen_workcenters) | Float | Written by `action_sbk_recalc_kitchen_duration` from operation template's `compute_expected_duration` |
| Variance Min | `x_sbk_variance_min` (`mrp.workorder`, kitchen_workcenters) | Float, stored | `duration − x_sbk_kitchen_expected_min` |
| Estimated Cost | `x_sbk_estimated_cost` (`mrp.workorder`, kitchen_workcenters) | Float (Product Price), stored | `x_sbk_kitchen_expected_min / 60 × workcenter_id.costs_hour` |
| Actual Cost | `x_sbk_actual_cost` (`mrp.workorder`, kitchen_workcenters) | Float (Product Price), stored | `duration / 60 × workcenter_id.costs_hour` |
| Cost Variance | `x_sbk_cost_variance` (`mrp.workorder`, kitchen_workcenters) | Float (Product Price), stored | actual − estimated |
| Rework Count | `x_sbk_rework_count` (`mrp.workorder`, kitchen_workcenters) | Integer, NOT stored | Count of `southbrook.mi.check` where `x_sbk_rework_workorder_id == self.id` |
| Rework Cost | `x_sbk_rework_cost` (`mrp.workorder`, kitchen_workcenters) | Float (Product Price), NOT stored | Sum of rework WO duration × hourly rate |
| Downtime Min | `x_sbk_downtime_min` (`mrp.workorder`, kitchen_workcenters) | Float, NOT stored | Sum of linked `southbrook.kitchen.workcenter.downtime.duration_min` (active+closed) |
| Downtime Cost | `x_sbk_downtime_cost` (`mrp.workorder`, kitchen_workcenters) | Float (Product Price), NOT stored | Sum of linked downtime `downtime_cost` |

### Owned by `southbrook_mrp_kitchen_tools`

| Label | Field (model.field, owner) | Type | Computed from |
|---|---|---|---|
| Tool Readiness | `southbrook_tool_readiness_state` (`mrp.workorder`, tools) | Selection: not_checked / ready / warning / blocked | Default `not_checked`; written by `action_check_tool_readiness` |
| Tool Readiness Message | `southbrook_tool_readiness_msg` (`mrp.workorder`, tools) | Text | Written alongside the state with a human-language reason |

## The tool readiness state machine

| State | Meaning | Set by |
|---|---|---|
| `not_checked` | Default. No one has run the readiness gate against this WO yet. | Default on WO creation |
| `ready` | All required tools are present, sharp/calibrated/clean, none over their next-service date. | `action_check_tool_readiness` when all reqs satisfied |
| `warning` | All MANDATORY tools are present, but some non-mandatory under-stocked. | `action_check_tool_readiness` |
| `blocked` | At least one mandatory tool is missing, dull, uncalibrated, or out of inventory. | `action_check_tool_readiness` |

The constant `READINESS_STATE_SELECTION` lives at module scope in
`southbrook_mrp_kitchen_tools/models/mrp_workorder.py` — referenced
by the tool consumption and asset code too.

**The gate**: `button_start` (the native Odoo "Start" action on a
WO) is overridden by the tools addon. If
`southbrook_tool_readiness_state == 'blocked'`, the override raises
`UserError("Tool readiness blocks start: <msg>")` and refuses to
start. Operator MUST resolve the block (get the tool from the crib,
replace a dull bit) and re-run **Check Tool Readiness** before
proceeding.

How the check works (the body of `action_check_tool_readiness`):

1. Collect tool requirements from BOTH the workcenter
   (`workcenter_id.southbrook_tool_requirement_ids`) AND the
   operation (`operation_id.southbrook_tool_requirement_ids`).
2. For each requirement, call `_available_asset_count(req)` which
   searches `southbrook.tool.asset` filtered by `is_available=True`
   and EXCLUDING assets flagged `needs_sharpening`,
   `needs_calibration`, or `needs_cleaning`.
3. Compare available vs required `min_quantity`. If short and the
   requirement's `is_mandatory=True` → `blocked`. If short and
   non-mandatory → `warning`. If all reqs met → `ready`.
4. Write `southbrook_tool_readiness_state` AND
   `southbrook_tool_readiness_msg` (the human-readable detail).

## The downtime model

`southbrook.kitchen.workcenter.downtime` is its own table, owned by
`southbrook_mrp_kitchen_workcenters`. Schema:

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Default "Downtime" |
| `state` | Selection: **draft** / active / closed / cancelled | Default draft, tracked, indexed |
| `workcenter_id` | M2O → `mrp.workcenter` | Required, indexed, ondelete=cascade |
| `workorder_id` | M2O → `mrp.workorder` | Optional, ondelete=set null |
| `production_id` | M2O → `mrp.production`, related to `workorder_id.production_id` | Stored related |
| `date_start` | Datetime | Required, default now |
| `date_end` | Datetime | Indexed |
| `duration_min` | Float, stored compute (editable backfill) | `date_end − date_start` in minutes |
| `reason` | Selection (13 reasons) | Required, indexed |
| `notes` | Text | Free-form |
| `responsible_id` | M2O → `res.users` | Default current user |
| `downtime_cost` | Float, stored compute | `duration_min/60 × workcenter_id.costs_hour` |

The 13 reasons: `material_not_available`, `drawing_issue`,
`machine_breakdown`, `tool_change`, `setup_time`,
`color_finish_changeover`, `waiting_previous_operation`,
`waiting_quality_approval`, `rework`, `operator_unavailable`,
`subcontract_delay`, `maintenance`, `other`.

State machine:

- `draft` → `active`: `action_start` (also stamps `date_start = now()`)
- `active` → `closed`: `action_close` (stamps `date_end = now()`)
- any → `cancelled`: `action_cancel`

**The link back to the WO**: `workorder_id` (M2O, ondelete=set null).
The WO's `x_sbk_downtime_min` and `x_sbk_downtime_cost` compute
fields search downtime rows where `workorder_id == self.id` AND
`state IN ('active', 'closed')` — `draft` rows aren't counted (a
draft hasn't actually happened yet) and `cancelled` rows are
explicitly excluded.

## Your daily flow

**1. Operator side — pre-start ritual:**

- Open the WO on your shop-floor view.
- Look at the tool readiness statusbar at the top. If it's
  `not_checked` (grey), tap **Check Tool Readiness**. The button
  is gated by `group_tool_operator` — every operator has this
  group by default.
- If the state lands on `ready` (green), tap **Start**. The native
  `button_start` runs unimpeded.
- If `warning` (amber), READ the message. It'll say e.g. "blade
  set #14 below recommended stock (mandatory ok)". Decide whether
  to proceed or fetch more before starting.
- If `blocked` (red), READ the message and resolve. Tap **Start**
  too early and you'll see "Tool readiness blocks start: <msg>"
  raised — Odoo won't move you to `progress`.

**2. Operator side — during run:**

- The WO is in `progress`. The native `duration` field accumulates
  real run time. Behind the scenes, every minute of `duration`
  feeds into `x_sbk_actual_cost` (via the cost compute) and
  `x_sbk_variance_min` (via the variance compute).
- If you have to pause for a tool change, log it as **downtime**
  (lesson 1.6). The downtime row's `workorder_id` should point
  back to YOUR WO so the cost gets attributed correctly. Otherwise
  the pause shows up as your run-time variance.

**3. Planner side — variance review:**

- End of day, open **Southbrook PM → Capacity** for the pivot or
  filter MOs by `x_sbk_total_variance_min > 60` (over an hour
  late vs estimate).
- Per WO, the breakdown is in the form's Southbrook fields:
  `x_sbk_kitchen_expected_min` (what we thought it would take),
  `duration` (what it actually took), `x_sbk_variance_min`
  (delta), `x_sbk_downtime_min` (how much of the delta is
  attributable to downtime).
- Variance net of downtime = real overrun. If `variance_min ≈
  downtime_min`, the operation was on plan and downtime ate the
  buffer. If `variance_min >> downtime_min`, the operation itself
  ran slow — the template estimate may be wrong, or the operator
  needs help.

## Common mistakes + how to recover

**"Operator says they tapped Start and got a 'Tool readiness blocks
start' error. They've already gone to the crib and grabbed the
bit."**

The state didn't auto-clear when they got the new bit. Tap **Check
Tool Readiness** again. The check now sees the new asset (or the
old asset's flag cleared because someone updated
`needs_sharpening = False`) and the state flips to `ready`. Then
Start works.

**"Variance is showing +145 min but the operator's run was on
time."**

Two common causes:
1. `x_sbk_kitchen_expected_min` was never written (the operation
   template's `compute_expected_duration` wasn't called because the
   operation lacks `x_sbk_operation_template_id`). The variance =
   `duration − 0 = duration`. Fix: open the MO, tap **Recalc All
   Workorder Durations** which fires the template formula across
   all WOs.
2. Downtime wasn't logged. The pause hours sit inside `duration`
   and inflate variance. Fix: file the downtime row retroactively
   with `state='closed'`, accurate `date_start` and `date_end`.

**"I logged downtime but it's not showing in
`x_sbk_downtime_min`."**

Check the downtime row's `state` and `workorder_id`. If `state =
draft`, the compute skips it (drafts don't count). If
`workorder_id` is empty (the operator filed downtime against the
workcenter but didn't pick a workorder), the compute can't
associate it to ANY single WO — it shows up in workcenter-level
metrics but not per-WO. Edit the row: set `workorder_id`, transition
to `active` or `closed`.

**"`southbrook_tool_readiness_state` is `ready` but mid-run the
operator says the bit broke."**

Readiness is a point-in-time gate. Once `ready` is written and
Start has fired, no live monitoring catches a tool breaking mid-run.
The operator logs downtime (reason: `tool_change`) and tap **Check
Tool Readiness** again before resuming. The state may flip to
`blocked` if no spare is in inventory — that's the system telling
you to halt, not a bug.

**"Tool consumption rows are bumping asset life faster than we
expected — assets that should last 200 uses are flipping to
`needs_sharpening` after 80."**

The consumption model's `_apply_to_asset_life` bumps
`asset.total_usage_qty` and decrements `asset.remaining_life_qty`
on every consumption row. If consumption is being logged
TWICE per WO (e.g. one row per panel × 5 panels instead of one row
per WO × 5 quantity), life burns 5× faster. Audit the consumption
list under the MO smart button.

## What the system is doing behind the scenes

The WO surface is **two addons cooperating**: kitchen_workcenters
owns variance + cost + downtime fields, kitchen_tools owns
readiness + consumption.

The variance compute (`_compute_x_sbk_variance` in kitchen_workcenters)
depends on `duration` and `x_sbk_kitchen_expected_min` — anytime
either changes, variance is re-derived synchronously. Storage means
the field is searchable for the "show me WOs with variance > X"
filter.

The cost compute (`_compute_x_sbk_costs`) depends on `duration`,
`x_sbk_kitchen_expected_min`, AND `workcenter_id.costs_hour` — so
re-pricing a workcenter's hourly rate ripples through every WO's
estimated and actual cost in one write.

The downtime aggregation (`_compute_x_sbk_downtime`) is NOT stored
because the downtime table is mutated heavily during a shift and
storing would mean every downtime save triggers a write on every
linked WO. Read on demand instead — the search domain is cheap
(one indexed FK lookup).

`_apply_to_asset_life` is the side effect that makes the
consumption model interesting. Each row creates writes to the
linked asset: `total_usage_qty += quantity`, `remaining_life_qty
-= quantity`, `last_used_date = now()`, `last_used_workorder_id =
self.workorder_id.id`. When `remaining_life_qty` hits zero, the
asset's `lifecycle_state` flips from `in_use` to
`needs_sharpening`. The nightly **Tool Asset Maintenance Sweep**
cron (cron_tool_asset_maintenance_sweep in
`southbrook_mrp_kitchen_tools/data/crons.xml`) walks all assets
and re-checks the `next_*_due_date` fields against today; overdue
assets get their `needs_*` flags set so the readiness gate catches
them.

## Quiz (5 questions, applied)

**1.** Operator taps Start. Native Odoo doesn't move the state to
`progress` — instead, a UserError pops up: "Tool readiness blocks
start: blade set #14 missing (mandatory)." Walk through what just
happened in the database.

> Native `button_start` was overridden by
> `southbrook_mrp_kitchen_tools/models/mrp_workorder.py:button_start`.
> The override checks `self.southbrook_tool_readiness_state`. It's
> `blocked` because either (a) Check Readiness was never run and
> the default state is `not_checked` (but then state would be
> `not_checked` not `blocked`), or more likely (b) Check Readiness
> was run earlier, found blade set #14 short and wrote
> `state='blocked'` + `msg='blade set #14 missing'`. The override
> raises `UserError`, native Start is aborted, state stays
> `pending` (or whatever it was). Operator must resolve, re-check,
> then retry.

**2.** The variance on a WO is +250 min but the downtime sum on
the same WO is 300 min. Is the operator slow or fast?

> Fast. Variance = `duration − expected = +250`. Downtime within
> that duration = 300. Run time net of downtime = `duration − 300
> = expected − 50` (50 min UNDER plan). The operator did the work
> 50 min faster than estimated, but a 300 min downtime event
> dragged the WO's total `duration` over the line. The variance
> field alone is misleading without the downtime breakdown — read
> both.

**3.** A `southbrook.kitchen.workcenter.downtime` row has `state =
draft`. The operator says "I filed that 2 hours ago — why isn't it
counted?"

> Drafts don't count. The compute `_compute_x_sbk_downtime`
> filters `state in ('active', 'closed')`. The row needs to be
> transitioned via `action_start` (→ active) or `action_close`
> (→ closed) before it appears in metrics. Drafts are scratch
> space; the operator likely meant to file it but didn't tap
> Start. Open the row, tap Start, tap Close once it's filled in.

**4.** You're auditing why `x_sbk_actual_cost` on a WO is $87.60
when the operator's run took 45 minutes. SB-EDGE is $65/h. Is the
math right?

> `45 min / 60 = 0.75 hr × $65/h = $48.75`. Expected actual cost
> is $48.75, not $87.60. The discrepancy means `duration` is more
> than 45 min OR the WO's `workcenter_id.costs_hour` isn't
> SB-EDGE's $65. Most likely the operator paused 35 min
> (unaccounted) and `duration` says 80 min: `80/60 × 65 = $86.67`
> close to $87.60. The fix: file the missing downtime so cost is
> attributed to downtime, not run time.

**5.** A planner wants to set up a recurring report: "WOs with
variance > 60 min in the last week." Which field do they filter
on, and is it stored (i.e. usable in a server filter)?

> Filter on `x_sbk_variance_min > 60` AND `date_finished >= today
> - 7`. `x_sbk_variance_min` is a stored compute on
> `mrp.workorder` (depends `duration`, `x_sbk_kitchen_expected_min`).
> Storage means the filter can run in PostgreSQL — it's
> efficient. The list view inherit doesn't currently expose this
> field by default but a saved search with a domain
> `[('x_sbk_variance_min', '>', 60), ('date_finished', '>=',
> '2026-06-10')]` works.

---

## What this lesson does NOT cover

- The MO-side fields (`x_sbk_total_*`, Kitchen tab) → lesson 15.2.
- The BoM extensions that drive the operation templates → lesson 15.4.
- Workcenter form and the alternative chain → lesson 15.5.
- MO Kanban + search filters → lesson 15.6.
- MO ↔ cutlist / hardware / production package → lesson 15.7.
- Daily operator routine at each station → Course 1 lessons 1.2-1.5.
- Logging downtime as an operator (the touchscreen flow) → Course 1 lesson 1.6.
- The MI engine's check catalog → Course 3 lesson 3.1.
