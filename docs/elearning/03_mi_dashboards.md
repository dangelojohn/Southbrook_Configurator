---
course: 3 — Floor Management
chapter: 3.1
title: Manufacturing Intelligence Dashboards — At-a-Glance Shop Floor Health
duration: 30 minutes
audience: Production Manager (runs the floor, owns shop-wide throughput and on-time delivery)
prereqs: Lesson 2.5 (reading an MI report), basic Odoo navigation, knowing what a manufacturing order is
custom_modules: southbrook_manufacturing_intelligence, southbrook_mrp_pm, southbrook_premium_orchestration
---

# Manufacturing Intelligence Dashboards — At-a-Glance Shop Floor Health

## Who this lesson is for

You're the **Production Manager**. Your job is to look at the floor once an
hour, see what's actually going wrong, and put the right operator or planner
on the right problem. This lesson covers the four Southbrook-specific dashboards
that surface that information — what each one measures, where the numbers come
from, and what to do when one of them crosses a line.

## Where this lives on the site

Everything in this lesson lives under the **Southbrook PM** top-level menu. Sign
in at **southbrookcabinetry.space/odoo** as a user in the *Southbrook PM* group,
then:

> **Southbrook PM → Dashboard** — the workcenter KPI kanban (the home screen)
> **Southbrook PM → Ready Queue** — confirmed MOs waiting to release
> **Southbrook PM → In Production** — MOs currently running
> **Southbrook PM → Late Orders** — past deadline, not done, not cancelled
> **Southbrook PM → Floor Load** — every workcenter, grouped by active
> **Southbrook PM → Family Throughput** — cabinet-family level KPI
> **Southbrook PM → MI Checks** — every active check across the shop
> **Southbrook PM → MI Production Board** — production packages with MI status

The first one — **Dashboard** — is what you open at 7:00am. The rest are drill-down
targets when something on the Dashboard turns amber or red.

## What your screen shows

### Southbrook PM → Dashboard (the workcenter KPI kanban)

One kanban card per active workcenter, defined by
`southbrook_mrp_pm.view_southbrook_pm_kanban` on `mrp.workcenter`. Each card
shows four numbers and the OEE target:

- **In Queue** (`southbrook_pm_inflight_count` on `mrp.workcenter`) — open work
  orders pinned to this station right now.
- **Done Today** (`southbrook_pm_throughput_today`) — work orders this station
  finished since midnight.
- **Late** (`southbrook_pm_late_count`) — work orders touching this station
  whose MO `date_deadline` is past and state is not `done`/`cancel`.
- **Equipment** (`southbrook_pm_equipment_alerts`) — count of
  `maintenance.equipment` records attached to this workcenter with a non-good
  `southbrook_condition` pill.
- **OEE Target** (`oee_target` on `mrp.workcenter`, seeded at **85.0%**) — the
  native Odoo field, set during install by
  `southbrook_mrp_pm/data/workcenters.xml` for the 8 SB stations
  (SB-SAW, SB-EDGE, SB-CNC-BORE, SB-ASSY, SB-DOOR, SB-HW, SB-QC, SB-PACK). The
  Southbrook-custom field `x_sbk_oee_target` on the same model (default 0.85)
  is a parallel target consumed by the kitchen-workcenter views; both exist.

### Southbrook PM → MI Production Board

A list of `sb.production.package` records decorated by **MI status**
(`x_mi_status` on `sb.production.package`, values `ok` / `review` / `blocked`).
Columns:

- **Name** — the package code.
- **MO** (`mo_id`) — the linked manufacturing order.
- **State** — the MO state.
- **MI Status** — colour-coded: red `blocked`, amber `review`, green `ok`.
- **MI Blockers** (`x_mi_blocker_count`) and **MI Warnings**
  (`x_mi_warning_count`) — totals per package.
- **MI Next Action** (`x_mi_next_action`) — the engine's one-line recommendation
  derived from the highest-severity check.

### Southbrook PM → MI Checks

The raw check list — every row is a `southbrook.mi.check` record, decorated by
severity (`blocker` / `warning` / `info`) and grouped by category
(`cut` / `production` / `assembly` / `install` / `cad` / `hardware`). Default
search filters drop you into `Blockers` grouped by `Category` so you see the
worst problems first.

### Per-MO Intelligence tab

On any manufacturing order form, the **Intelligence** notebook page
(`view_mrp_production_form_mi` inheriting `mrp.mrp_production_form_view`) shows
the same six fields scoped to that MO:

- **MI Status** (`x_mi_status` on `mrp.production`, widget=badge)
- **MI Next Action** (`x_mi_next_action`)
- **MI Blockers** / **MI Warnings** (`x_mi_blocker_count`, `x_mi_warning_count`)
- **Sheet Yield %** (`x_mi_yield_pct`) and **Waste Area m²** (`x_mi_waste_area_m2`)
- The full `x_mi_check_ids` list — every check linked to this MO, with severity,
  category, message, and recommendation.

A **Recompute Intelligence** button at the top of the tab calls
`action_recompute_manufacturing_intelligence` on `mrp.production`, which
re-runs the engine for just this MO. Use it when you've just fixed an upstream
issue and want the dashboard to catch up immediately.

## Your daily flow

**Start of day (7:00am, 10 min):**

1. Open **Southbrook PM → Dashboard**. Scan the eight workcenter cards.
   - All four metrics green or zero → no action.
   - **Late > 0** on any card → that station has past-deadline work touching it
     today; jump to **Late Orders** to see which MOs.
   - **Equipment > 0** → at least one piece of equipment at that station is
     flagged. Click the card, scroll to equipment list, check the condition
     pill — `red` is a breakdown, `amber` is a watch item.
2. Open **Southbrook PM → MI Production Board**. Sort by *MI Status* descending
   so `blocked` rows surface at the top.
   - Each `blocked` row will have an *MI Next Action* line; that's your first
     job. Click into the package → **Intelligence** tab → read the full check
     list to see what the engine actually found.
3. Open **Southbrook PM → Late Orders**. Anything that wasn't on yesterday's
   late list is a new escalation; pair it with a planner.

**Mid-day (every 2 hours, 5 min):**

- Refresh the **Dashboard**. The kanban fields are computed
  *at view-render time* — there is no `store=True` on
  `x_mi_workcenter_blocker_count` / `x_mi_workcenter_warning_count`, so the
  counts re-aggregate every time you reload the view.
- If a station's **In Queue** climbs without **Done Today** climbing, the
  station has stalled — go look.
- New blockers on the **MI Production Board** since morning → follow the *Next
  Action* line, then re-run **Recompute Intelligence** on the package once you
  believe it's fixed.

**End of day (4:30pm, 10 min):**

- Open **Southbrook PM → Family Throughput**. Compare `throughput_today` per
  family against the planner's plan for the day. A big gap on one family is
  tomorrow's planner conversation.
- Check that yesterday's `blocked` packages are now `ok` or `review`. Anything
  still `blocked` at end of day rolls into tomorrow's stand-up.

**Per investigation (drill-down from a red card):**

1. Click the workcenter card on the **Dashboard**. The form opens with the PM
   kanban inherit (`view_southbrook_pm_kanban_mi`) showing MI chips: `MI Blocked`,
   `MI Warnings`, or `MI Clear`.
2. Open the work orders list on the form — find the WO with the blocker.
3. From the WO, click through to its parent MO → **Intelligence** tab → check
   list.
4. The check `recommendation` field tells you the specific corrective action
   (e.g. "Split the part, select a larger sheet, or confirm a special-order
   blank before cutting"). That's what to ask the operator or planner.

## Common mistakes + how to recover

**"The Dashboard says SB-EDGE has 3 blockers but I'm standing in front of the
station and everything looks fine."**

The kanban fields are not stored — they're a snapshot computed when the view
renders. If you opened the Dashboard 90 minutes ago and an operator has since
cleared the upstream issues, the chips lag the truth. **Reload the view** (F5
or click the menu again) to force a recompute. There's a deliberate design
note in `mrp_workcenter.py`: `@api.depends_context("uid")` means each user's
view aggregates fresh, but only on render.

**"A check says 'Missing cutlist' on an MO that clearly has one."**

The engine writes checks only when something is recomputed. If you re-linked a
cutlist after the last engine run, the old check is stale. Click **Recompute
Intelligence** on the MO's **Intelligence** tab — `_recompute_production` will
delete every existing check for that MO (via
`_unlink_existing_checks(production=production)`) and rewrite the current
state from scratch.

**"I approved a package this morning but it's still showing as `review` on
the MI Production Board."**

The package-level MI status is recomputed by `_recompute_package`, not by
your approval. The hourly **MI Stage-Gate Refire** cron sweeps open MI gates,
but it only re-fires stage gates — it won't recompute a package whose
underlying check list hasn't changed. Open the package and click **Recompute
Intelligence** to force the rewrite.

**"Late Orders shows an MO whose deadline I just extended."**

The Late Orders action uses a domain with `time.strftime` evaluated at query
time, so it'll pick up the new deadline on the next reload — but only after
the MO write has committed. Reload after you save.

**"Sheet yield is showing 0% on a package with a perfectly normal cutlist."**

`x_mi_yield_pct` is reset to 0.0 explicitly when the engine can't find a
cutlist (the `else` branch of `_recompute_production`). If the cutlist exists
but you still see 0%, the cutlist has no `line_ids`, or every line has
zero `length_mm`/`width_mm`/`qty`. Fix the cutlist, then recompute.

## What the system is doing behind the scenes

(For the curious manager and the supervisor on call when an incident comes in.)

The dashboards read from three places:

1. **`southbrook.mi.check`** — the per-event check rows, written by the
   engine on the abstract model `southbrook.mi.engine`. Each row carries
   `severity` (`blocker`/`warning`/`info`), `category` (`cut`/`production`/
   `assembly`/`install`/`cad`/`hardware`), `message`, `recommendation`, and
   either `production_id` or `production_package_id`. The list is sorted by
   `severity_rank` (0=blocker, 1=warning, 2=info) so the most urgent rows
   render first.

2. **Computed counters on `mrp.production` and `sb.production.package`** —
   `x_mi_status`, `x_mi_blocker_count`, `x_mi_warning_count`,
   `x_mi_next_action`, `x_mi_yield_pct`, `x_mi_waste_area_m2`,
   `x_mi_edge_band_m`. These are written by `_recompute_production` and
   `_recompute_package`, which read the checks the engine just generated and
   roll them into single fields the views can index.

3. **Non-stored aggregates on `mrp.workcenter`** —
   `x_mi_workcenter_blocker_count` and `x_mi_workcenter_warning_count`,
   computed on view render with `@api.depends_context("uid")`. The trade-off
   is documented in `mrp_workcenter.py`: storing them would require depending
   on every MI/MO state transition, which deadlocks the save path during high
   shift volume. So the counters are re-aggregated each time the kanban opens.

**Refresh cadence — the orchestration crons.** The five
*Southbrook Premium Orchestration* crons (defined in
`southbrook_premium_orchestration/data/ir_cron.xml`) are what keep dashboards
honest without anyone clicking anything:

| Cron name | Interval | What it does |
|---|---|---|
| Southbrook: Recompute Project Readiness | every 30 min | Recomputes readiness mask (BOM/drawings/tooling/labour) on project tasks. |
| Southbrook: Refire MI Stage-Gate Checks | every 1 hour | Re-evaluates open MI stage gates so a gate clears the moment its upstream condition flips. |
| Southbrook: Backfill Order Analytics | every 6 hours | Captures analytics rows for confirmed SOs that don't have one yet. |
| Southbrook: Weekly Planning Baseline | every 7 days (Sun 02:00) | Creates and runs the fresh weekly `mrp.planning.run` baseline. |
| Southbrook: Quality Dry-Run Nightly | daily (~03:00) | Walks the project tree, scores against DQ ruleset, writes a dry-run report. |

The 1-hour **MI Stage-Gate Refire** is the one most relevant to your daily
flow — it's why a check that was blocking yesterday afternoon can be green by
the time you come in. If you need a faster pass, click **Recompute
Intelligence** on the individual MO or package.

## Quiz (5 questions, applied)

**1.** It's 9:30am. The Dashboard shows SB-CNC-BORE with `In Queue: 12,
Done Today: 0, Late: 3, Equipment: 1`. What's the first thing you check?

> **Equipment: 1** — a non-good condition pill on a piece of equipment at the
> CNC. If a machine is down, *Done Today: 0* is explained. Click into SB-CNC-BORE
> on the dashboard, scroll to the equipment list, see which equipment is in
> `red` or `amber` condition. That's the root cause; the late count and the
> queue depth are both downstream of it.

**2.** A package shows MI Status `blocked` with one check: *"Production
package has no cutlist"*. You know the cutlist was attached an hour ago.
What do you do?

> Open the package, go to the **Intelligence** tab, click **Recompute
> Intelligence**. The engine's `_recompute_package` deletes all existing
> checks for the package and rewrites them from scratch — the stale
> *"Missing cutlist"* row will be gone if the cutlist is now linked.

**3.** Your morning Dashboard shows SB-EDGE with 0 blockers and 4 warnings.
By 11am the chip still says `4 MI Warnings`, but you know the planner cleared
two checks. What's going on?

> The kanban metrics are not stored — they're computed when you open the
> view. The chip you see is from the morning's render. Reload the view; the
> `_compute_southbrook_mi_kpis` re-aggregates and the chip drops to 2.

**4.** Throughput on the cabinet family `SB-BASE` was 18 today, plan was
24. Where do you go next?

> **Family Throughput** shows you the gap. To find the cause: drill into the
> `SB-BASE` family card → list of MOs in flight → look at MOs with a non-`ok`
> MI status. If MI is clean across the board, the gap is a planning issue,
> not an intelligence issue — bring it to the planner with the actual
> numbers, not just the gap.

**5.** A check has severity `warning`, category `cut`, message
*"Sheet yield is 39.2%"*. Should you stop the cut?

> No — `warning` doesn't block; only `blocker` does (look for red
> decoration on the MI Production Board). The recommendation reads
> *"Review nesting, duplicate panels, and sheet selection"*. Pass it to the
> planner or PLM engineer to review *before* the next cut; the current cut
> can proceed. Below 45% yield is the engine's warning threshold (in
> `_recompute_package`).

---

## What this lesson does NOT cover

- The recommendation queue you approve from Fabio — that's lesson 3.2
  (`03_hermes_fabio_approval.md`).
- The per-workcenter OEE drill-down — that's lesson 3.3 (`03_oee.md`).
- Reading an individual MI report row in full detail — covered in lesson 2.5.
- Native Odoo MRP work-order and MO lifecycle — Odoo's own eLearning track.
- The Hermes Console at hermes.odooiq.com (sysadmin recommendations queue) —
  Course 7 lesson `07_hermes_sysadmin.md`.
