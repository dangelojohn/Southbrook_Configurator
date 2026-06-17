---
course: 12 — Kitchen Ops Deep Dive
chapter: 12.5
title: Floor Load + Workcenter Bottlenecks — The Read-Side Analytics
duration: 35 minutes
audience: Production Planner + Production Manager (the two who walk the floor with this board)
prereqs: Course 2 lesson 2.3 (Bottleneck-Aware Scheduling). This lesson goes deeper into the KPI computes, alternative routing, and amber/red banding.
custom_modules: southbrook_mrp_pm, southbrook_mrp_kitchen_workcenters, southbrook_premium_orchestration, southbrook_manufacturing_intelligence
---

# Floor Load + Workcenter Bottlenecks — The Read-Side Analytics

## Who this lesson is for

You're the planner or production manager walking the floor with the
Workcenter Bottlenecks board open on your tablet. Course 2 lesson
2.3 gave you the operational flow (read the board, schedule MOs,
reroute on breakdowns). This lesson goes inside the data: how each
KPI is COMPUTED, why the bottleneck KPI you see may already be
stale, how the `alternative_workcenter_ids` relationship feeds
re-routing, and how the structural vs live bottleneck flags
disagree.

Get the compute timing wrong and you'll make scheduling decisions
based on yesterday's load numbers — that's the most common rookie
mistake.

## Where this lives on the site

For the planner:

> **Kitchen Ops → Workcenter Bottlenecks**

Default kanban view on `mrp.workcenter`. Action is
`action_workcenter_bottleneck_board` in
`southbrook_premium_orchestration/views/workcenter_bottleneck_views.xml`.
Domain filter: `active = True`.

For the production manager's walk-around:

> **Southbrook PM → Floor Load**

Same underlying data, different framing. Owned by
`southbrook_mrp_pm/views/pm_menus.xml`. The PM uses this on a tablet
while walking the floor; the planner uses Kitchen Ops →
Bottlenecks from a desk.

For the per-workcenter detail:

> **Manufacturing → Configuration → Work Centers → \<click one\>**

The OOTB Odoo workcenter form, extended with the Southbrook fields.

## What your screen shows

Each tile on the Workcenter Bottlenecks kanban (using Odoo's stock
mrp.workcenter kanban — see the "behind the scenes" for why
Southbrook doesn't ship a custom one):

- **Workcenter name + code** (`name`, `code` on `mrp.workcenter`).
  E.g. "Panel Saw / CNC Nesting (SB-SAW)".
- **In-Flight WOs** (`southbrook_pm_inflight_count`) — count of
  work orders at this station in `pending` / `waiting` / `ready` /
  `progress`. Live, no cache.
- **Done Today** (`southbrook_pm_throughput_today`) — count finished
  here since midnight (`state = done` AND `date_finished >=
  today 00:00`).
- **Late MOs** (`southbrook_pm_late_count`) — count of MOs with at
  least one WO at this station whose `date_deadline` has passed
  and which aren't done.
- **Equipment Alerts** (`southbrook_pm_equipment_alerts`) — count
  of `maintenance.equipment` records at this station whose
  `southbrook_condition` is anything other than `good` (i.e.
  `fair` / `watch` / `critical` / `offline`).

On the per-workcenter form, the Southbrook tab shows the planner /
configuration fields:

- **Station type** (`x_sbk_station_type`) — Selection: `cutting`,
  `cnc`, `edge_banding`, `assembly`, `finishing`, `engineering`,
  `quality`, `subcontract`, etc.
- **Bottleneck flag** (`x_sbk_is_bottleneck`) — Boolean,
  **configuration**, NOT live state.
- **Allows parallel jobs** (`x_sbk_allows_parallel_jobs`) — True
  for stations that can run multiple WOs concurrently.
- **Max panel size** (`x_sbk_max_panel_length_mm`,
  `x_sbk_max_panel_width_mm`) — operations whose cutlist line
  exceeds this can't route here.
- **Supported materials** (`x_sbk_supported_material_ids`).
- **Required skills** (`x_sbk_required_skill_ids`).
- **Default setup time** (`x_sbk_default_setup_time_min`).
- **Changeover time** (`x_sbk_changeover_time_min`).
- **OEE target** (`x_sbk_oee_target`).
- **Planning notes** (`x_sbk_planning_notes`) — Text.
- **Alternative workcenters** (`alternative_workcenter_ids`) —
  Many2many to self. The reroutable backups.

## The four KPI computes — how each is calculated

Defined in `southbrook_mrp_pm/models/mrp_workcenter.py`. All four
are NOT stored — each page load re-runs the search:

### `southbrook_pm_inflight_count`

```python
Wo.search_count([
    ("workcenter_id", "=", wc.id),
    ("state", "in", ["pending", "waiting", "ready", "progress"]),
])
```

**The "how busy is this station now?" metric.** Counts WOs that are
queued, waiting on prerequisites, ready to start, or running. The
metric grows as the planner schedules more MOs and shrinks as WOs
move to `done` or `cancel`.

Important: `waiting` state means the WO has unfinished predecessor
WOs (cutting must finish before edge banding can start). So a
high inflight count includes WOs that aren't physically at the
station yet — they're queued because the upstream isn't done.
Sub-filter to `state = ready` to see what's actually claimable.

### `southbrook_pm_throughput_today`

```python
Wo.search_count([
    ("workcenter_id", "=", wc.id),
    ("state", "=", "done"),
    ("date_finished", ">=", today_start),
])
```

**The coarse-grain throughput.** Counts WOs finished since midnight.
Resets daily. The fine-grain OEE compute (Course 3 lesson 3.3) is
the proper performance metric; this one is the "are we shipping?"
gut check.

### `southbrook_pm_late_count`

```python
Mo.search_count([
    ("state", "not in", ["done", "cancel"]),
    ("date_deadline", "<", now),
    ("workorder_ids.workcenter_id", "=", wc.id),
])
```

**The alarm bell.** Counts MOs (not WOs) whose deadline has passed
and which aren't done. The `workorder_ids.workcenter_id` join means
"this MO touches this station." A late count at SB-SAW cascades to
SB-EDGE three hours later because nothing has tape to band — the
cascade is the planner's job to predict.

### `southbrook_pm_equipment_alerts`

```python
Eq.search_count([
    ("workcenter_id", "=", wc.id),
    ("southbrook_condition", "in",
     ["fair", "watch", "critical", "offline"]),
])
```

**The maintenance signal.** `southbrook_condition` is a custom
Selection added by `southbrook_mrp_pm` to `maintenance.equipment`:
`good` / `fair` / `watch` / `critical` / `offline`. A `critical`
or `offline` machine at a workcenter means the station can run on
reduced capacity OR can't run at all — both surface as `> 0`
alerts.

### When are these computed?

All four have `@api.depends_context("uid")` — they re-evaluate on
EVERY page load for the requesting user. There's no cron pushing
updates; the data is read live from the underlying tables. The
upside: zero staleness, no cache invalidation. The downside: on
boards with many workcenters, each workcenter triggers four
search_counts on the database. The cost is manageable for the 18
Southbrook workcenters but would be painful at 200+.

## The amber / red banding — what drives it

The Workcenter Bottlenecks board uses Odoo's **stock** kanban view
on `mrp.workcenter` (see "behind the scenes" — Southbrook
deliberately didn't ship a custom kanban). The banding signals you
see come from the OOTB load vs capacity column:

- **Green** — load < 80% of capacity for the day.
- **Amber** — load 80-100% of capacity.
- **Red** — load > 100%.

`workcenter.load` is OOTB Odoo (sum of planned hours for in-flight
WOs at this station for today). `workcenter.capacity` is also OOTB
(hours per day from the resource calendar × time efficiency).

The Southbrook fields (`southbrook_pm_*`) are surfaced AS COLUMNS
on the kanban, but they don't drive the colour. If you want
colour-coded Southbrook KPIs, write a custom kanban that decorates
on the Southbrook fields directly. This is a documented gap that
the team hasn't prioritised.

## The bottleneck flag — what it means and what it doesn't

Two fields carry the word "bottleneck":

- **`x_sbk_is_bottleneck`** on `mrp.workcenter` — CONFIGURATION
  flag set at install time in
  `southbrook_mrp_kitchen_workcenters/data/mrp_workcenter_seed.xml`.
  It tells the planner "this is a structural constraint; never
  overload it." Doesn't change as work runs.
- **`x_mi_bottleneck_workcenter_id`** on `mrp.production` — LIVE
  field set by the MI engine. For a specific in-flight MO,
  identifies which workcenter is the constraint TODAY. Changes as
  conditions change.

The structural flag values (from the seed file):

| Code | Name | Bottleneck? | Alternative |
|---|---|---:|---|
| SB-SAW | Panel Saw / CNC Nesting | True | — |
| SB-EDGE | Edge Bander | True | — |
| SB-CNC-BORE | CNC Boring | True | CNC02 |
| SB-ASSY | Carcass Assembly | True | — |
| SB-DOOR | Door Hanging | False | — |
| SB-HW | Hardware Fitting | False | — |
| SB-QC | Quality Control | True | — |
| SB-PACK | Pack & Label | False | — |
| ENG01 | Design Review / Production Eng | False | — |
| CNC02 | CNC Router 02 (Backup) | False | SB-CNC-BORE |
| (extended: PAINT) | Paint Booth | True (in extended seed) | — |

Bottleneck stations get planning attention: the bottleneck board
sorts them to the top, the MI engine watches their idle minutes
more aggressively, and the planner shouldn't overload them.

## The `alternative_workcenter_ids` relationship

This is native Odoo `mrp.workcenter` field (many2many to self).
Southbrook adds the **reciprocity** convention via seed file:
SB-CNC-BORE → CNC02 AND CNC02 → SB-CNC-BORE. The reciprocity is
tested by `southbrook_mrp_kitchen_workcenters/tests/test_m1_workcenter_fields.py`.

The operation template
(`southbrook.kitchen.operation.template` — owned by
`southbrook_mrp_kitchen_workcenters`) reads BOTH `workcenter_id`
AND `alternative_workcenter_ids` when deciding which station can
run an operation step. This is the code path that lets you
re-route without re-writing the routing definition.

**Practical consequence**: when SB-CNC-BORE breaks down mid-day, the
planner opens the workcenter, sees CNC02 listed as the alternative,
and moves the unstarted WOs to CNC02. The operation template
accepts CNC02 because it was the listed alternative. No routing
edit needed.

The flip side: **SB-SAW, SB-EDGE, SB-ASSY, SB-QC, PAINT have NO
alternative.** They're irreplaceable in the current shop layout.
When one breaks, the only recovery options are:

1. Push the install date (PM + customer call).
2. Subcontract (if a `x_sbk_station_type = subcontract` routing is
   approved).
3. Triage which MOs survive (tightest deadline first).

Course 2 lesson 2.3 covers these recovery flows.

## When the bottleneck KPI lies

The KPIs are computed live but they read from the database state.
If the database is half-updated, the KPIs reflect the half-update.
The most common "the KPI lies" cases:

- **WO not closed at end-of-shift**: the operator forgot to tap
  Done. The WO stays in `progress`, so `southbrook_pm_inflight_count`
  is one too high for the next day's planning. Fix: educate
  operators on closing WOs; review the `progress`-state WO list
  daily.
- **WO assigned to wrong workcenter**: the planner moved an MO from
  SB-CNC-BORE to CNC02 but the WO's `workcenter_id` is still
  SB-CNC-BORE. Fix: re-confirm the MO so the WO regenerates from
  the updated routing.
- **`date_deadline` field auto-shifted by `_compute`**: native MRP
  recomputes deadlines when an MO is re-confirmed. If your late
  count flips from 4 to 0 overnight without anything finishing,
  the deadlines moved. Open the MOs and check `date_deadline` —
  it should match the install date.
- **Equipment condition stale**: someone flipped a machine to
  `good` after maintenance but forgot to mark another that just
  broke. The alert count stays the same; reality has moved.
  Cross-check with the actual floor.

The KPI is a SIGNAL, not the truth. Walk the floor; the floor is
the truth.

## Your daily flow

(Course 2 lesson 2.3 covers the basic flow. The detail additions
here:)

**Start of day (10 min):**

- Open Kitchen Ops → Workcenter Bottlenecks. **Sort the kanban by
  bottleneck flag** (configurable in the search bar — group by
  `x_sbk_is_bottleneck` and the True column floats to the top).
- For each bottleneck station:
  - Note `southbrook_pm_inflight_count`. Compare to yesterday's
    end-of-day note in `x_sbk_planning_notes`. If today's number is
    higher, the overnight queue grew (waiting WOs from upstream
    finishing).
  - Note `southbrook_pm_late_count`. Anything > 0 needs immediate
    triage.
  - Click into the workcenter, look at `alternative_workcenter_ids`.
    If there's a backup, you have a reroute option; if not, you
    don't.

**Mid-day check (5 min, around 11:00 and 14:00):**

- Refresh. The inflight counts may have shifted as morning WOs
  finished. The throughput-today count should be tracking to half
  of the day's plan by lunch.
- If a bottleneck's `southbrook_pm_equipment_alerts` increased
  since morning, a machine broke — drop everything and check.

**End of day (5 min):**

- Update each bottleneck's `x_sbk_planning_notes` with the
  end-of-day count for tomorrow's reference: "EOD: 12 inflight, 8
  done today, 0 late, 0 equipment alerts."
- Cross-check the late count is consistent with the at-risk badges
  on the Kitchen Jobs board.

## Common mistakes + how to recover

**"My inflight count says 8 but I can see 12 work orders queued at
the station."**

The 4 missing are in `cancel` or `done` state (closed) and aren't
counted, OR they're attached to MOs that were cancelled (the WO
state is `cancel` too). Open the workcenter's WO list, look at the
state column. The count is `pending / waiting / ready / progress`
only.

**"Done Today shows 0 at SB-CNC-BORE but the operator finished 5
WOs this morning."**

Either (a) the WOs weren't actually moved to `done` state — the
operator hit some other button (clock out, pause), or (b) the
`date_finished` wasn't written. Both happen when the floor portal
disconnects mid-action. Recovery: open Manufacturing → Work Orders,
filter by SB-CNC-BORE + today's date, check the state column. Any
in `progress` or with `date_finished` blank: edit manually and
mark Done with the actual finish time.

**"The late count went from 0 to 7 overnight at SB-ASSY but nothing
ran overnight."**

The compute uses `date_deadline` on the MO, not on the WO. When
midnight rolled over, 7 MOs whose deadline was "today" became
"yesterday" and tripped the late filter. The cabinets aren't
physically late yet; the planning baseline is. This is the
signal to escalate to PM, not panic — the deadline was already
known, you just hadn't acted on it.

**"I rerouted from SB-CNC-BORE to CNC02 but the workcenter's
inflight count on SB-CNC-BORE didn't drop."**

The route change updates the OPERATION TEMPLATE's allowed
workcenters, not the existing WOs' `workcenter_id`. To actually
move the WOs, open them and change `workcenter_id` on each. Or
cancel the WOs and let confirmation regenerate them against the
new routing.

**"Equipment alert count is 1 but I can't find the bad machine."**

The compute counts equipment records at this workcenter with
condition `fair`/`watch`/`critical`/`offline`. Open the
workcenter's linked `maintenance.equipment` list (under the
workcenter form, look for the equipment tab or filter on
`workcenter_id`). Find the one whose condition isn't `good`. If
the count is 1 but no equipment shows up there, the
`workcenter_id` on the equipment record might be wrong — check
the field and fix.

## What the system is doing behind the scenes

The Workcenter Bottlenecks board action
(`action_workcenter_bottleneck_board`) **deliberately doesn't
specify a custom view_id**. Odoo falls back to the stock kanban +
list + form views for `mrp.workcenter`. The comment in
`workcenter_bottleneck_views.xml` explains why: in Odoo 19,
`mrp.workcenter` has load-order quirks around capacity / load
fields that fail view validation during `-u` even when the
fields exist in `fields_get`. Falling back to stock views is
safer.

The four Southbrook KPI fields ARE visible on the stock kanban
because they exist on the model, but the OOTB kanban template
doesn't include them by default — the planner sees them on the
form view, not the kanban tile. This is a UI gap; surfacing them
on the kanban requires a view inheritance the team hasn't shipped.

The `x_sbk_is_bottleneck` flag is configuration, set in
`mrp_workcenter_seed.xml`. The seed runs at install time and on
`-u southbrook_mrp_kitchen_workcenters`. Flipping it via the UI
is allowed but discouraged — the seed re-runs on update will NOT
re-overwrite (the seed uses `noupdate=0` for the new records but
`noupdate=1` for existing field updates, intentionally).

The `alternative_workcenter_ids` field is native Odoo m2m to
self. The Southbrook seed sets the reciprocity (A→B AND B→A).
The reciprocity test catches future regressions.

The MI engine's `x_mi_bottleneck_workcenter_id` on
`mrp.production` is the LIVE bottleneck for that MO at the time
of the last MI recompute. The recompute fires on MO save and on
the hourly MI gate refire cron. So `x_mi_bottleneck_workcenter_id`
can change between morning and afternoon as conditions shift
(equipment goes down, alternative workcenter comes online).

## Quiz (5 questions, applied)

**1.** You open the Workcenter Bottlenecks board at 08:00. SB-SAW
shows `inflight=22, late=2, equipment_alerts=0`. CNC02 shows
`inflight=3`. The cron just ran at 07:30. What's the right
sequence of actions?

> SB-SAW is dangerously overloaded (22 inflight, typical 6-10).
> The 2 late MOs are already off-plan. (1) Open SB-SAW's WO list,
> sort by `date_planned_start`. Identify the 8-12 WOs that can
> roll to tomorrow — defer them. (2) Check
> `alternative_workcenter_ids` on SB-SAW — it's empty, no reroute.
> (3) The cascade hits SB-EDGE in 3 hours; pre-warn the edge bander
> operator about reduced volume. (4) Tell the PM the 2 late MOs
> need install-date conversation TODAY. CNC02's low inflight is
> unrelated (different routing path); don't move SB-SAW work to
> CNC02 — different operations.

**2.** A planner notices `southbrook_pm_throughput_today` at 0 on
SB-CNC-BORE at 14:00 but knows the operator ran 4 WOs since
morning. What are the two most likely causes?

> (1) The WOs are in `progress` state, not `done`. The operator
> hit Start but didn't tap Done — they're still "in flight" in the
> system. Recovery: educate the operator, walk them through closing
> WOs. (2) The WOs ARE done but `date_finished` is blank (floor
> portal disconnect mid-tap). Recovery: open each WO, set
> `date_finished` to the actual finish time. The count flips on
> the next page refresh.

**3.** SB-EDGE's `southbrook_pm_late_count` is 4 at 09:00 with
zero new MOs running. What happened between yesterday's close and
this morning?

> Midnight rolled over and 4 MOs whose `date_deadline` was
> yesterday became late. These were already known-late at end of
> shift but the alarm was suppressed until the date crossed. The
> action: escalate to PM for install-date negotiation, identify
> what tomorrow's plan deprioritises to drain the backlog.

**4.** A planner moves an unstarted WO from SB-CNC-BORE to CNC02
by editing the WO's `workcenter_id` field directly. The next cron
tick, the WO's workcenter_id is back to SB-CNC-BORE. What's the
cause?

> Some downstream automation re-derived `workcenter_id` from the
> routing. Native Odoo's MO recompute can do this on certain
> state transitions. The right way to reroute is via the operation
> template's `alternative_workcenter_ids` (which is already set
> for the SB-CNC-BORE ↔ CNC02 pair) so the routing allows both;
> then the WO assignment should persist. If it's still reverting,
> open the MO and look at the routing — the operation step might
> have `workcenter_id` hard-coded to SB-CNC-BORE without the
> alternative listed.

**5.** A PM asks "why doesn't the kanban tile colour reflect the
Southbrook KPIs? SB-EDGE shows 26 inflight but the tile is green."

> The action falls back to Odoo's stock kanban view because Odoo
> 19's `mrp.workcenter` has view-validation quirks that broke a
> custom kanban we tried earlier. The stock kanban colour comes
> from native `load` vs `capacity` columns (today's scheduled
> hours vs the resource calendar's hours). The Southbrook KPIs
> are columns on the form, not the kanban. This is a known UI
> gap; the workaround is to use the list view (sortable by
> Southbrook columns) for triage instead of relying on tile
> colour.

---

## What this lesson does NOT cover

- The basic scheduling flow and rerouting playbook → Course 2
  lesson 2.3.
- The MI engine's per-MO live bottleneck
  (`x_mi_bottleneck_workcenter_id`) and how it differs from the
  structural one → Course 2 lesson 2.3 + 2.5.
- OEE (the proper performance metric beyond throughput_today) →
  Course 3 lesson 3.3.
- Native Odoo `mrp.workcenter` resource calendar, capacity, load
  computes → Odoo's own training.
- Per-operator daily flow at each station → Course 1 lessons
  1.2-1.5.
- Authoring routings + operation templates → developer-side, out
  of e-learning scope.
