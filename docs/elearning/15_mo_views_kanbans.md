---
course: 15 — Manufacturing Module Deep Dive
chapter: 15.6
title: MO Views, Kanbans, Search Filters — What's Custom vs Native
duration: 25 minutes
audience: Production Manager + Planner using the MO list/kanban every day
prereqs: Lesson 15.1, Lesson 15.2, Course 3 lesson 3.1 (MI dashboards), comfortable with native Odoo list/kanban/search
custom_modules: southbrook_mrp_pm, southbrook_mrp_kitchen_workcenters, southbrook_manufacturing_intelligence
---

# MO Views, Kanbans, Search Filters — What's Custom vs Native

## Who this lesson is for

You spend your day in the MO list, the workcenter kanban, the
capacity pivot, or the Floor Manager portal. This lesson tells you
which of those views are Southbrook-custom (and what to expect of
them) vs native Odoo (where stock behaviour applies). The honest
answer: **Southbrook adds less than the brief suggests** — there's
no MO Kanban with state swimlanes, no Gantt, no color-coded due-date
heatmap. What IS there is a workcenter kanban with KPI tiles, an MI
chip overlay, an MO Intelligence notebook page, an MI checks list,
and a capacity pivot/graph. This lesson maps the whole surface so
you stop hunting for views that don't exist.

## Where this lives on the site

> **Southbrook PM → Dashboard** — `mrp.workcenter` kanban with KPI tiles
> **Southbrook PM → Ready Queue / In Production / Late** — `mrp.production` filtered lists
> **Southbrook PM → Family Throughput** — `southbrook.cabinet.family` kanban
> **Southbrook PM → Capacity** — `mrp.workorder` pivot + graph
> **Southbrook PM → MI Checks** — `southbrook.mi.check` list (default filters: blockers + group-by-category)
> **Southbrook PM → MI Packages** — `sb.production.package` list
> **/my/southbrook/floor** — Floor Manager portal (separate from Odoo backend, tablet-styled)
> **/odoo/manufacturing → Manufacturing Orders** — native MO list (Southbrook adds 4 columns)

## What your screen shows — view-by-view inventory

### 1. Southbrook PM Dashboard kanban (the workcenter kanban)

**Owner**: `southbrook_mrp_pm` (`view_southbrook_pm_kanban` in
`pm_dashboard.xml`).
**Model**: `mrp.workcenter`.
**Default group-by**: `active` (so on/off workcenters split).
**Domain**: `active = True` from the action.
**What each card shows**:
- Workcenter name + code
- `southbrook_pm_inflight_count` (In-flight WOs — pending/waiting/ready/progress)
- `southbrook_pm_throughput_today` (Done Today)
- `southbrook_pm_late_count` (Late MOs)
- `southbrook_pm_equipment_alerts` (Equipment Alerts)
- OEE % footer (from `oee_target`)

**MI overlay**: `view_southbrook_pm_kanban_mi` (in
`southbrook_manufacturing_intelligence/views/pm_kanban_inherit.xml`)
inherits the above and injects chips:
- `<t t-if="x_mi_workcenter_blocker_count">` → red chip
  (`o_sb_mi_chip_blocker`), shows blocker count
- `<t t-elif="x_mi_workcenter_warning_count">` → amber chip
  (`o_sb_mi_chip_warning`), shows warning count
- `<t t-else>` → clear chip (`o_sb_mi_chip_clear`)

The CSS lives in `southbrook_mrp_pm/static/src/scss/dashboard.scss`
(backend bundle). The chip is what tells you at a glance which
workcenter has an MI-flagged MO running through it.

### 2. Family Throughput kanban

**Owner**: `southbrook_mrp_pm`.
**Model**: `southbrook.cabinet.family`.
**What each card shows**: family name, late count footer.
No decoration; plain card. Useful for the manager who plans by
product family rather than workcenter.

### 3. Capacity pivot + graph

**Owner**: `southbrook_mrp_pm` (`view_pm_capacity_pivot`,
`view_pm_capacity_graph` in `pm_capacity.xml`).
**Model**: `mrp.workorder`.
**Pivot**: rows = `workcenter_id`, columns = `date_start`
(interval=day), measure = `duration_expected`.
**Graph**: bar, stacked, `date_start × workcenter_id`, measure
`duration_expected`.
**Default domain**: state in pending / waiting / ready / progress
**Context**: `search_default_group_by_workcenter: 1`
**No custom search filter**.

Look at this view weekly. Anything above 480 min (1 shift) per WC
per day is over-committed. Anything above 720 min (1.5 shifts) is
in over-time territory.

### 4. Ready Queue / In Production / Late lists

**Owner**: `southbrook_mrp_pm`. All three actions target
`mrp.production` with different domains and the native list view
(no Southbrook list inherit on those actions specifically):

| Action | Domain | Context |
|---|---|---|
| `action_pm_ready_queue` | `state in ('confirmed', 'progress')` | `search_default_group_by_state: 1` |
| `action_pm_in_production` | `state = 'progress'` | (none) |
| `action_pm_late` | `state not in ('done', 'cancel') AND date_deadline < now` | (none) — domain uses `time.strftime` |

**Note on the Late action**: the domain evaluates
`time.strftime('%Y-%m-%d %H:%M:%S')` at action-load time. If you've
had Odoo running for a week without restart, the `now` cutoff
**still updates correctly** because the domain string is re-eval'd
on every action open — but this is a subtle Odoo behaviour to know.

### 5. MO list — column extensions

**Owner**: `southbrook_mrp_kitchen_workcenters`
(`view_mrp_production_tree_sbk_kitchen`).
**Inherits**: `mrp.mrp_production_tree_view`.
**Columns added**:
- Install Due Date (`x_sbk_install_due_date`)
- Kitchen Project (`x_sbk_kitchen_project_id`)
- Cabinet Code (`x_sbk_cabinet_code`)
- Priority Level (`x_sbk_priority_level`)

**No decoration rules**. The list doesn't colour rows red for late,
amber for at-risk, or green for on-track. Visual urgency is on YOU
to interpret. (If you want decoration, file a ticket — it's a
~10-line view inherit.)

### 6. MO form — notebook pages

Covered in detail in lesson 15.2. Summary:
- **Kitchen tab** (`view_mrp_production_form_sbk_kitchen`) — project
  linkage, complexity, totals.
- **Intelligence tab** (`view_mrp_production_form_mi`) — MI badge,
  checks list, recompute button.

### 7. MI Checks list

**Owner**: `southbrook_manufacturing_intelligence`
(`view_southbrook_mi_check_list`, `view_southbrook_mi_check_search`
in `manager_dashboard_views.xml`).
**Model**: `southbrook.mi.check`.
**Decoration**:
- `decoration-warning` when `severity == 'warning'`
- `decoration-danger` when `severity == 'blocker'`
- `decoration-info` when `severity == 'info'`

**Search filters** (this is the ONE place rich search lives):

| Filter | Domain |
|---|---|
| Blockers | `severity = 'blocker'` |
| Warnings | `severity = 'warning'` |
| Category: Cut | `category = 'cut'` |
| Category: Production | `category = 'production'` |
| Category: Assembly | `category = 'assembly'` |
| Category: Install | `category = 'install'` |
| Group by Category | group_by `category` |
| Group by Severity | group_by `severity` |
| Group by Package | group_by `production_package_id` |

Default-filter is `blockers`; default group-by is `category`. So the
first thing you see is the blocker count grouped by where in the
flow it's hurting (cut, production, assembly, install).

### 8. MI Packages list

**Owner**: `southbrook_manufacturing_intelligence`
(`view_southbrook_mi_package_list`).
**Model**: `sb.production.package`.
**Decoration**:
- `decoration-success` when `x_mi_status == 'ok'`
- `decoration-warning` when `x_mi_status == 'review'`
- `decoration-danger` when `x_mi_status == 'blocked'`

This is the green/amber/red list. The production package is the
per-MO bundle (lesson 15.7) so seeing it red means the MO can't
ship.

### 9. Floor Manager portal

**Owner**: `southbrook_mrp_pm`.
**Routes**: `/my/southbrook/floor` and `/my/southbrook/floor/<wc_id>`
(views in `views/floor_template.xml`).
**Bundle**: `southbrook_mrp_pm/static/src/scss/floor.scss` (frontend
asset bundle, touch-friendly).
**Audience**: `group_floor_manager` (portal users with the Floor
Manager group). Members can see their station's WO queue, start/finish
WOs, and toggle equipment condition.

This is the only **mobile / tablet** surface in the stack. Native
Odoo doesn't render an MO Kanban for tablet; this fills the gap for
the floor-walking manager.

## What's NOT there (and why it matters)

These features are referenced in old briefs but DO NOT exist in
code as of this writing:

| Feature | Status | What you do instead |
|---|---|---|
| MO Kanban with state swimlanes | **Not implemented** | Use Ready Queue / In Production / Late actions; each is a filtered list grouped by state |
| MO Gantt chart | **Not implemented** | Capacity pivot is the closest analogue (workorder-level, not MO-level) |
| MO Calendar view | **Not implemented** | Native Odoo MO calendar works on `date_planned_start` — no Southbrook customization |
| Color rules on MO list (overdue=red, etc.) | **Not implemented** | Decoration only on MI Checks + MI Packages lists |
| Search filter for station_type | **Not implemented** on MO; only on workcenter list (group-by Station Type) |
| Search filter for bottleneck workcenter | **Not implemented** | `x_mi_bottleneck_workcenter_id` is reserved on `mrp.production` but engine doesn't write it yet |
| Search filter for MI status | **Not exposed** on MO list; you can filter the MO list by typing `x_mi_status:blocked` in the global search, but no saved filter exists |
| Per-workcenter MO drill-down | **Partial** | Click into a workcenter on the dashboard → opens its Equipment / Tool sub-views; for the MOs touching that WC, use Capacity pivot grouped by workcenter |
| Mobile breakpoint on backend | **Not implemented** | Backend is desktop-only; Floor Manager portal is the tablet path |

If a feature you need is in this "not there" list, the realistic
options are: (a) file a ticket; (b) use a saved search you create
yourself in the global search box; (c) write a small view inherit
yourself (Odoo studio works for non-developers for trivial cases).

## Your daily flow

**1. Manager morning (10 min):**

- **Southbrook PM → Dashboard**. Scan the workcenter kanban for
  red MI chips (`o_sb_mi_chip_blocker`) and high Late MO counts.
  This is the fastest "where's the fire" read.
- Click the red chip on a workcenter → filters to MOs with blockers
  at that workcenter. Open each one, read the Intelligence tab,
  decide release vs hold.
- **Southbrook PM → MI Checks** (default-filtered blockers,
  grouped by category). Cross-check the dashboard with the
  check-level view to make sure you haven't missed a category.

**2. Mid-day planning (10 min):**

- **Southbrook PM → Capacity** pivot, range = next 5 days. If
  any workcenter × day cell > 480 min, that day is over-committed.
  Right-click → pivot drill-down to see which MOs are loading it.
- **Southbrook PM → Late Orders**. Should be 0 most days.
  Anything here means a deadline has already passed; either reset
  the deadline (with chatter note explaining why) or expedite the
  MO.

**3. End of day (5 min):**

- **Southbrook PM → MI Packages**. Anything decorated red
  (`decoration-danger`, `x_mi_status='blocked'`) is tomorrow's
  problem. Make sure the right person is paged before you leave.

## Common mistakes + how to recover

**"The Ready Queue list shows nothing but I just confirmed 5
MOs."**

The action's domain is `state in ('confirmed', 'progress')`. If
your MOs jumped straight to `done` (because they had no work to
do — fully stocked, no routing), they won't appear. Check the MO's
state in the global MO list.

**"The MI Checks list is empty for an MO I know has blockers."**

The MI Checks list is a flat view of all checks across all MOs. If
one MO's checks aren't showing, either (a) the MI engine hasn't
been run since the issue arose — hit Recompute on the MO; (b) the
default filter `blockers` is hiding warnings — clear the filter to
see all severities.

**"I want to filter MOs by Kitchen Project but the search doesn't
show that field."**

The search-filter inherit for the MO list doesn't expose Kitchen
Project. Workaround: open the Kitchen Project record
(`sb.kitchen.project`), use its smart button to navigate to its
MOs. Or build your own saved filter with domain
`[('x_sbk_kitchen_project_id', '=', <id>)]`.

**"The Capacity pivot shows an empty cell but I scheduled the WO
for that day."**

The pivot's row dimension is `date_start` on the workorder. If
`date_start` is empty (the MO is `confirmed` but unscheduled), the
WO doesn't appear in any cell. Plan the MO to populate `date_start`.

**"The Floor Manager portal shows 0 WOs but the operator says
they have 8."**

The portal scopes by `group_floor_manager` membership. The
operator and the floor manager are different people. If the
**manager** isn't in the right group, the portal returns empty.
Check `res.users → group_ids` on the manager account.

## What the system is doing behind the scenes

The Southbrook view surface is sparser than the brief implies
because Odoo native MO views are already capable for most planner
needs. The Southbrook value-add is:

1. **The MI overlay** — chips on the workcenter kanban that surface
   per-MO MI verdicts at the workcenter level. This is the
   highest-density signal on the platform: one glance at the
   dashboard tells you which stations have problems.
2. **The Capacity pivot** — turns workorder-level data into a
   planner-readable shift-load matrix.
3. **The MI Checks list** — a flat, filterable view of every check
   the engine has written, decorated by severity. Without this, the
   manager would have to open each MO individually to see blockers.
4. **The MO column extensions** — install due, kitchen project,
   cabinet code, priority — show on the native MO list without
   needing a separate Southbrook list view.
5. **The Floor Manager portal** — the only tablet-friendly path.

What ISN'T built (no MO swimlane Kanban, no Gantt, no calendar) is
deliberate scope rather than oversight. Native Odoo Calendar +
Gantt (Enterprise-only feature; we're on CE) cover those use cases
on the OOTB MO model.

**v19 cron behaviour** — none of the Southbrook MO views run their
own crons. The MI engine pass that populates the chip values runs
nightly + hourly via `southbrook_premium_orchestration` (lesson
2.4) so the dashboard is honest by morning and stays fresh through
the day.

## Quiz (5 questions, applied)

**1.** You see a red MI chip on SB-EDGE's workcenter dashboard
tile showing the number 2. What does this mean and what's your
first click?

> 2 MOs that touch SB-EDGE have `x_mi_blocker_count > 0`
> (aggregate count from `view_southbrook_pm_kanban_mi`). Clicking
> the chip → opens a filtered MO list of those 2 MOs. Open the
> first MO, scroll to the Intelligence tab, read the blocker rows
> and the `x_mi_next_action` text to decide release vs hold.

**2.** A trainee says "I want a Kanban view that shows MOs in
columns by state — Draft / Confirmed / In Progress / Done — like
the native CRM pipeline." Does this exist on Southbrook MOs?

> No. There's no Southbrook-custom MO Kanban with state swimlanes.
> The closest is **Southbrook PM → Ready Queue** which is a LIST
> view with `search_default_group_by_state` context — visually a
> stacked grouped list, not a kanban swimlane. Filing a ticket for
> a real Kanban view is reasonable; it's ~50 lines of XML.

**3.** The MI Checks list is grouped by category by default.
You want to see them grouped by severity instead. How?

> Open **Southbrook PM → MI Checks**, click the search/filter
> dropdown, untick "Category" group-by, tick "Severity" group-by.
> The filter `view_southbrook_mi_check_search` defines both
> `group_category` and `group_severity` — they're mutually
> exclusive at one time. The change persists for your session;
> use the favourite-search feature to save it.

**4.** The Capacity pivot shows SB-CNC-BORE at 600 min Tuesday.
The native MRP module shows 8 MOs touching SB-CNC-BORE on
Tuesday. Are these consistent?

> Maybe. 600 min / 8 MOs = 75 min per MO average. If the
> per-MO `duration_expected` on the touching workorder averages
> 75 min, yes consistent. If 8 MOs but only 4 have non-zero
> `duration_expected` (the others are 0 because they don't have
> an operation template applied yet), the pivot only counts the
> 4 — could be 150 min × 4. Drill into the pivot cell to see the
> contributing workorders.

**5.** Your sysadmin wants to add a calendar view showing MOs by
`x_sbk_install_due_date`. What's the cleanest way?

> Write a view-inherit XML on `mrp.production` adding a
> `<calendar>` view with `date_start="x_sbk_install_due_date"`.
> Ship it in a small follow-up addon that depends on
> `southbrook_mrp_kitchen_workcenters` (the field's owner). Add
> a menu action under Southbrook PM → "Install Calendar". ~30
> lines of XML. Native Odoo handles the rendering — no Python
> required.

---

## What this lesson does NOT cover

- MO field walkthrough → lesson 15.2.
- Workorder fields + tool readiness + downtime → lesson 15.3.
- BoM math + cut constants → lesson 15.4.
- Workcenter form + alternative chain + operation templates → lesson 15.5.
- MO ↔ cutlist / hardware / production package → lesson 15.7.
- MI engine check definitions → Course 3 lesson 3.1.
- Premium orchestration crons → Course 2 lesson 2.4.
- Floor Manager portal daily flow → Course 3 lesson 3.x (separate).
- Native Odoo MO list / form / kanban / search → Odoo native training.
