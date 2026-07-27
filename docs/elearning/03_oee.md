---
course: 3 — Floor Management
chapter: 3.3
title: OEE per Workcenter — What `oee_target` Means and When to Investigate
duration: 30 minutes
audience: Production Manager (interprets per-workcenter OEE and decides what corrective action to send to which operator)
prereqs: Lesson 3.1 (MI dashboards), basic familiarity with `mrp.workcenter` and the eight SB stations
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_pm, southbrook_manufacturing_intelligence
---

# OEE per Workcenter — What `oee_target` Means and When to Investigate

## Who this lesson is for

You're the **Production Manager**. OEE is the single number you'll get asked
about most — by the planner ("is SB-EDGE really the bottleneck?"), by the
SAMI investment committee ("are we hitting world-class?"), and by yourself
when a station feels slow but the queue depth doesn't show it. This lesson
covers what OEE means in Southbrook's specific implementation: which fields
feed it, which dashboard tile shows it, what `oee_target` is actually
benchmarking against, and which operator conversation to have when each
factor sags.

## Where this lives on the site

> **Southbrook PM → Dashboard** — the kanban shows the OEE target per
> workcenter at the bottom of each card.
> **Manufacturing → Configuration → Work Centers** (or **Southbrook PM →
> Floor Load**) — the workcenter form, where the OEE target lives and
> where the downtime breakdown can be drilled into.

There is no standalone "OEE report" page in v1 — OEE shortfall analysis is
done by inspecting downtime, cycle-time variance, and rework metrics on the
work-order list under each workcenter.

## What your screen shows

### The Dashboard card (per workcenter)

Each kanban card on **Southbrook PM → Dashboard** shows four live metrics
(*In Queue*, *Done Today*, *Late*, *Equipment* — see lesson 3.1) and the
**OEE Target** in the card footer. The target rendered is the native Odoo
`oee_target` field on `mrp.workcenter`, seeded at **85.0%** by
`southbrook_mrp_pm/data/workcenters.xml` for all eight Southbrook stations:

| Code | Name | `oee_target` | `costs_hour` |
|---|---|---|---|
| `SB-SAW` | Panel Saw / CNC Nesting | 85.0 | $85/hr |
| `SB-EDGE` | Edge Bander | 85.0 | $65/hr |
| `SB-CNC-BORE` | CNC Boring | 85.0 | $80/hr |
| `SB-ASSY` | Carcass Assembly | 85.0 | $60/hr |
| `SB-DOOR` | Door Hanging | 85.0 | $55/hr |
| `SB-HW` | Hardware Fitting | 85.0 | $50/hr |
| `SB-QC` | Quality Control | 85.0 | $40/hr |
| `SB-PACK` | Pack & Label | 85.0 | $35/hr |

There is a **second** OEE target field on the same model:
**`x_sbk_oee_target`** (`mrp.workcenter`, defined in
`southbrook_mrp_kitchen_workcenters/models/mrp_workcenter.py`, default
**0.85** as a 0..1 ratio, widget `percentage`). It serves the
kitchen-workcenter views that read 0..1, while the native `oee_target`
serves the PM dashboard that reads percent. Both should agree (0.85 ↔ 85.0%).
The `x_sbk_oee_target` field is set per workcenter on the form view
(`southbrook_mrp_kitchen_workcenters/views/mrp_workcenter_views.xml`); the
native `oee_target` is seeded by the PM data file mentioned above.

### The workcenter form — the fields that feed OEE

When you open a workcenter (e.g. **SB-EDGE**), the form shows the kitchen
extension fields used to compute the three OEE factors:

- **`oee_target`** (native, percent) — the benchmark the dashboard compares
  against. 85.0% is the industry-standard "world-class" threshold and what
  Southbrook adopted at install per the JTBD recommendation in
  `southbrook_mrp_pm/data/workcenters.xml`.
- **`x_sbk_oee_target`** (0..1) — Southbrook-custom mirror, default 0.85,
  for the kitchen views.
- **`x_sbk_default_setup_time_min`** — minutes added per WO for setup.
- **`x_sbk_changeover_time_min`** — minutes when an operation changes
  material/finish/tool.
- **`x_sbk_is_bottleneck`** — Theory-of-Constraints configuration flag.
  Bottleneck stations have stricter scrutiny on availability shortfalls.
- **`costs_hour`** (native) — used by the downtime cost rollup.
- **`x_sbk_allows_parallel_jobs`** — whether the station can run multiple
  WOs in flight at once.

### The work-order list per workcenter

The work-order list under any workcenter is the actual data source for OEE
calculation. Relevant `mrp.workorder` fields:

- **`duration`** (native) — actual minutes worked. The denominator for
  Performance.
- **`duration_expected`** (native) — Odoo's expected duration.
- **`x_sbk_kitchen_expected_min`** — parallel expected duration computed
  from Southbrook's operation-template formula (not Odoo's compute). The
  planner audits which engine produced which estimate.
- **`x_sbk_variance_min`** — `duration − x_sbk_kitchen_expected_min`.
  Positive = over budget.
- **`x_sbk_downtime_min`** — sum of attached downtime durations on this
  WO. The denominator for Availability calculation.
- **`x_sbk_downtime_cost`** — sum at workcenter's `costs_hour`.
- **`x_sbk_rework_count`** — number of rework checks pointing at this WO
  via `x_sbk_rework_workorder_id` on `southbrook.mi.check`. The Quality
  signal.
- **`x_sbk_rework_cost`** — rework duration cost attributed back to this
  WO.

### The downtime list

`southbrook.kitchen.workcenter.downtime` is the table that feeds the
Availability factor. Every row carries:

- **`workcenter_id`** — which station.
- **`workorder_id`** — optionally, the specific WO that was running.
- **`date_start`** / **`date_end`** / **`duration_min`** — the window.
- **`reason`** — one of 13 reasons (verbatim from the model):
  - `material_not_available` — Material Not Available
  - `drawing_issue` — Drawing / Spec Issue
  - `machine_breakdown` — Machine Breakdown
  - `tool_change` — Tool Change
  - `setup_time` — Setup Time
  - `color_finish_changeover` — Color / Finish Changeover
  - `waiting_previous_operation` — Waiting on Previous Operation
  - `waiting_quality_approval` — Waiting on Quality Approval
  - `rework` — Rework
  - `operator_unavailable` — Operator Unavailable
  - `subcontract_delay` — Subcontract Delay
  - `maintenance` — Planned Maintenance
  - `other` — Other
- **`state`** — `draft` / `active` / `closed` / `cancelled`.
  Cancelled rows are excluded from rollup; active and closed both count.
- **`downtime_cost`** — `(duration_min / 60) × costs_hour`.

## Your daily flow

### The OEE formula (how Southbrook computes it)

**OEE = Availability × Performance × Quality.** Each factor is a 0..1 ratio
that is computed per workcenter from the work-order and downtime tables.

- **Availability** = `productive_time / scheduled_time`
  - `scheduled_time` = sum of `duration_expected` (or `x_sbk_kitchen_expected_min`)
    on all WOs scheduled to the station today.
  - `productive_time` = `scheduled_time − sum(x_sbk_downtime_min)` for the
    same set of WOs. Any downtime row in state `active` or `closed`
    counts; `cancelled` does not.
  - A station with 8 hours of scheduled work and 47 minutes of logged
    downtime has Availability = (480 − 47) / 480 = 0.902.

- **Performance** = `expected_duration / actual_duration`
  - For each completed WO: `x_sbk_kitchen_expected_min / duration`.
  - Aggregated per workcenter as the WO-weighted average.
  - A WO that took 30 minutes but was expected to take 22 has Performance
    = 22/30 = 0.733. Cycle-time variance directly degrades this.

- **Quality** = `good_parts / total_parts`
  - For Southbrook this is computed by looking at MI checks of severity
    `blocker` or `warning` in category `assembly`/`hardware`/`install` that
    point back at WOs on this workcenter via
    `x_sbk_rework_workorder_id` — i.e. the WO that produced a defect
    bad enough to need rework.
  - Quality = 1 − (rework_count / total_workorders) for the period.

OEE = the three numbers multiplied. A station at 0.90 × 0.85 × 0.95 = 0.726,
which is below the 0.85 target — investigation needed.

### Start of day (10 min)

1. Open the **Dashboard**. Note the OEE target on each card (85.0% across
   the board, by seed).
2. For each station, look at the Done Today vs In Queue ratio mentally — a
   station that didn't move much yesterday will have OEE problems showing
   up in your weekly review.
3. Open **Manufacturing → Reporting → Work Orders Performance** (Odoo
   native) or any pivot view grouped by workcenter for the day prior to
   see actual yesterday-vs-expected duration ratios.

### Per investigation (when OEE on a station crosses the target)

A station's calculated OEE has dropped below its target. **Decompose into
the three factors first** — never attack OEE as a single number, because
the corrective action depends entirely on which factor sagged.

**1. Low Availability** (the station was idle when it shouldn't have been)
- Open the downtime list filtered to that workcenter for the period:
  *Southbrook PM → (workcenter)* → downtime tab.
- Group by `reason`. The top reason category is your Pareto winner.
- Match reason to corrective action:
  - `machine_breakdown` → equipment maintenance log; coordinate with
    Equipment Owner.
  - `material_not_available` → planner conversation — material readiness
    check before MO release (lesson 2.2).
  - `waiting_previous_operation` → upstream bottleneck; check the prior
    station in the routing.
  - `setup_time` / `tool_change` → planner can sequence WOs to share setup;
    operator can pre-stage tools.
  - `color_finish_changeover` → planner sequence again (cluster same-colour
    WOs); applies hardest at SB-EDGE and finishing stations.
  - `operator_unavailable` → HR / shift coverage.
  - `waiting_quality_approval` → QC throughput; talk to QC lead.

**2. Low Performance** (the station was running but slower than expected)
- Open the WO list for the period, filtered to the workcenter.
- Sort by `x_sbk_variance_min` descending. The top rows are the WOs that
  bled time.
- For each, compare `duration` to `x_sbk_kitchen_expected_min`. Common
  causes:
  - Operator just learned the operation — variance high on first few WOs,
    recovers. Coach, don't escalate.
  - Operation template estimate is wrong — `x_sbk_kitchen_expected_min`
    consistently low across many operators on the same op. Talk to the
    planner about recalibrating the template (via
    `action_sbk_recalc_kitchen_duration` on the WO).
  - Material is harder than expected — check whether `x_sbk_complexity_factor`
    on the parent MO is set correctly.

**3. Low Quality** (the station produced rework)
- Open **Southbrook PM → MI Checks**, filter category to `assembly` /
  `hardware` (or `install` if you're managing finishing stations),
  group by `production_id` to see which MOs the rework is concentrated on.
- For each affected MO, check the WO that produced the defect — via the
  `x_sbk_rework_workorder_id` link on the check.
- Match to corrective action:
  - Same operator across multiple rework events → coaching conversation.
  - Same operation across operators → spec issue; talk to PLM about the
    cut spec or the routing.
  - Same upstream component → root cause is at the prior station; rework
    here is symptomatic.

### Per investigation (the OEE-shortfall decision tree)

| Symptom | Most likely factor | First check |
|---|---|---|
| Station went idle for blocks of time | Availability | Downtime list, group by `reason` |
| Station ran but every WO was over plan | Performance | WO list, sort by `x_sbk_variance_min` desc |
| Station ran on time but produced defects | Quality | MI Checks, category `assembly`/`hardware`, group by `production_id` |
| All three sag together | Upstream | Check the prior station in the routing — root cause is rarely here |

### End of day (5 min)

- Note any station where today's OEE was meaningfully under target. A
  one-day blip is noise; a three-day pattern is a campaign.
- For the bottleneck stations (`x_sbk_is_bottleneck = True`), shortfall is
  P0 — capture the cause in the next planning meeting.

## Common mistakes + how to recover

**"The kanban shows `OEE Target 85.0%` — where do I see actual OEE?"**

The dashboard card shows the **target**, not the live actual. There is no
single computed OEE field on the workcenter in v1 — actual OEE is computed
on demand by looking at the three factor sources (workorders, downtime,
rework checks) for a chosen period. Open the work-order list and the
downtime list filtered to the workcenter and compute the three factors. A
future MI engine extension will write a stored actual; until then, the
dashboard target is the benchmark, not the readout.

**"OEE on SB-EDGE looks bad but every downtime row is `cancelled`."**

`cancelled` rows are deliberately excluded — that's the inspector's
"this wasn't really downtime" override (see the model docstring). If you
think a row was incorrectly cancelled, find it, open it, and reopen via
the `action_start` button (which transitions back to `active`).

**"My calculated Performance is over 1.0 — that's not possible."**

It is, when actual was faster than expected. Performance > 1 means the
operator beat the operation-template estimate. Two possibilities: the WO
genuinely went well (no action), or the template estimate is too generous
(talk to the planner; recalibrate via
`action_sbk_recalc_kitchen_duration`).

**"A downtime row I just closed shows `duration_min = 0`."**

The `_compute_duration` compute fires on `date_start` + `date_end`. If
you closed it via **Close** (which calls `action_close`) the `date_end`
is now; if the time difference rounds to under 1 minute, you'll see 0.
The field is writable — backfill an estimate manually. The model docstring
flags this case ("an operator who forgot to start the timer can backfill
an estimate").

**"The `oee_target` and `x_sbk_oee_target` on a workcenter disagree."**

They should always agree (0.85 ↔ 85.0%). If they don't, someone has
edited one without the other. The native `oee_target` is what the PM
dashboard renders; the `x_sbk_oee_target` is what the kitchen view shows.
Update both to keep the displayed target consistent across screens.

## What the system is doing behind the scenes

OEE isn't a single Python field — it's a *derived metric* aggregated from
three input tables when you look at it. The fields above are what's
**actually stored**:

- `mrp.workcenter.oee_target` — the percent target seeded by
  `southbrook_mrp_pm/data/workcenters.xml` at install.
- `mrp.workcenter.x_sbk_oee_target` — the 0..1 mirror, default 0.85,
  declared in `southbrook_mrp_kitchen_workcenters/models/mrp_workcenter.py`.
- `mrp.workorder.duration` and `mrp.workorder.x_sbk_kitchen_expected_min`
  — actual and expected minutes per WO. The latter is recomputed by
  `action_sbk_recalc_kitchen_duration` from the operation-template formula
  (driver value × complexity factor).
- `mrp.workorder.x_sbk_variance_min` — stored, computed by
  `_compute_x_sbk_variance` as `duration − x_sbk_kitchen_expected_min`.
- `mrp.workorder.x_sbk_downtime_min` — *not* stored (`store=False`),
  recomputed on view render by aggregating
  `southbrook.kitchen.workcenter.downtime` rows where
  `workorder_id == self.id` and `state in ('active', 'closed')`.
- `mrp.workorder.x_sbk_rework_count` and `x_sbk_rework_cost` — also not
  stored; counted from `southbrook.mi.check` records pointing at the WO
  via `x_sbk_rework_workorder_id`.

The `southbrook.kitchen.workcenter.downtime` model is CE-safe (no
dependency on Enterprise maintenance/quality) and is the canonical
source for Availability. The 13 `DOWNTIME_REASONS` enumerated in the
model are what populate the Pareto chart you build when Availability is
the suspect factor.

**Bottleneck handling.** The `x_sbk_is_bottleneck = True` configuration
flag on the workcenter tells two systems to treat the station with
elevated scrutiny: (a) the planner avoids parallel routes through it;
(b) the MI engine marks extended idle time on it as P0. The flag is
*configuration* — set in the workcenter seed XML, not edited on the fly.
A bottleneck station whose OEE drops below target is an immediate
investigation; a non-bottleneck station whose OEE drops is a watch item.

**Refresh cadence.** None of the OEE source fields are recomputed by a
scheduled cron — every read is on demand. The five **Southbrook
Orchestration** crons (lesson 3.1) drive readiness and MI stage gates,
not OEE. If you need the variance and downtime aggregates to reflect a
just-closed downtime row, save the row and reload the WO list; the
non-stored computes fire on render.

## Quiz (5 questions, applied)

**1.** SB-EDGE's calculated OEE for the week is 0.71 (target 0.85).
Availability is 0.83, Performance is 0.96, Quality is 0.89. Which
factor do you investigate first, and where do you look?

> **Availability**. 0.83 is the lowest of the three and the furthest
> below benchmark (~0.95). Open the downtime list filtered to SB-EDGE
> for the week, group by `reason`. The top reason category is your
> root cause to attack first.

**2.** A downtime row says `reason = color_finish_changeover` and lasted
35 minutes. Is that downtime "real" for OEE purposes, or is it normal
operating time?

> Real for Availability — the row is in state `closed` (active and
> closed both count). But the corrective action is to **sequence WOs by
> colour**, not to fix the machine. Same-colour WOs back-to-back reduce
> the changeover count. Bring it to the planner with the downtime
> Pareto.

**3.** SB-CNC-BORE's Performance is 0.62 — everything is running 30-40%
over expected. The same operator has worked the station all week.
What's most likely, and what action do you take?

> Either the operation-template estimate is too tight (most likely after
> several rounds of consistently-over WOs across operators), or one
> specific operation has a wrong template. Sort the WO list by
> `x_sbk_variance_min` desc, open the worst row, compare `duration` to
> `x_sbk_kitchen_expected_min`. If the same operation surfaces
> repeatedly, talk to the planner about recalibrating the template via
> `action_sbk_recalc_kitchen_duration`.

**4.** A workcenter's calculated Quality is 0.78. You open
**Southbrook PM → MI Checks** filtered to the workcenter; almost every
rework check points at the same operator. What conversation do you
have, and with whom?

> Coaching conversation with the operator. The pattern is
> operator-specific, not operation-specific. Pull the specific MI
> checks (their `message` and `recommendation` fields tell you exactly
> what went wrong) and walk through them with the operator. If the
> pattern crossed multiple operators, the conversation shifts to PLM
> (cut-spec) instead.

**5.** The dashboard card for SB-ASSY shows OEE Target 85.0%, but
the form view for SB-ASSY shows `x_sbk_oee_target = 0.50`. Which is
right, and what do you do?

> They are out of sync — someone edited the kitchen field without
> updating the native field (or vice versa). The dashboard card reads
> native `oee_target` (85.0%) and the kitchen views read
> `x_sbk_oee_target` (0.50). Decide which is correct for the station's
> realistic target, then update *both* so every screen shows the same
> benchmark. Default for a healthy station is 0.85 / 85.0%.

---

## What this lesson does NOT cover

- Logging downtime as an operator — that's lesson 1.6
  (`01_logging_downtime.md`).
- The MI engine's per-package check rollup — lesson 3.1
  (`03_mi_dashboards.md`).
- Native Odoo OEE reporting at the Manufacturing → Reporting level — Odoo's
  own eLearning track covers the OOTB pivots and graphs.
- Recalibrating an operation template — covered in lesson 2.3
  (`02_bottleneck_scheduling.md`) and 4.2 (`04_cut_specs.md`).
- Equipment maintenance cycles — covered in Course 7 (sysadmin).
