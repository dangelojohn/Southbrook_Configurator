---
course: 14 — Project Module Deep Dive
chapter: 14.7
title: Project Reporting — Per-Project Metrics, Throughput, Late-Task Drill-Down
duration: 30 minutes
audience: Project Manager + Production Manager (anyone who has to defend "is the shop healthy?" to leadership)
prereqs: Lesson 14.1 (architecture); lesson 14.3 (readiness); Course 2 lesson 2.5 (Reading MI Reports — the manufacturing side)
custom_modules: southbrook_project_mrp, southbrook_project, southbrook_premium_orchestration
---

# Project Reporting — Per-Project Metrics, Throughput, Late-Task Drill-Down

## Who this lesson is for

You're the PM whose Monday morning starts with "how was last week?"
and you want to answer it with two clicks instead of a spreadsheet
export. Or you're the production manager presenting to leadership
and you need the slide that shows "X jobs ready, Y blocked, Z at
risk" without making it up. This lesson is the project-side
reporting surface — what's pre-aggregated, where it lives, what
counts as a "late" task, and how to export when the dashboards
don't quite cover the question.

Course 2 lesson 2.5 covers MI (Manufacturing Intelligence) reports
— that's the *manufacturing* lens. Course 12 lesson 12.6 will
cover the Kitchen Ops report grid. This lesson is the *project*
lens: rollups that read from `project.project` and `project.task`,
not from `mrp.production`.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo**.

> **/odoo/project → any project (form)** — the project form. Smart
> buttons + the (optional) mission-control kanban tile show
> per-project rollups.

> **/odoo/project → any project → Action → Southbrook Data Quality
> Dry Run** — fires `action_southbrook_data_quality_dry_run`,
> creating a `southbrook.project.data.quality.report` record listing
> data-quality issues (orphan MOs, missing install dates, queue
> overlaps, equipment count mismatches).

> **Settings → Technical → Database Structure → Data Quality
> Reports** — the list of past dry-run reports for audit.

> **(project form) → Manufacturing Jobs / Blocked Jobs / Review
> Jobs / Ready Jobs / Unscheduled Jobs / etc.** — drill-down
> buttons on the project form, each filtered to a different
> readiness/risk slice. Catalogued below.

> **/odoo/project (kanban)** — if you've activated the
> mission-control kanban (lesson 14.6), each project tile shows
> the rollup badges + a "Stop / Review / Clear" mission prompt.

## What your screen shows

### The 17 project-level rollup fields

`project.project` carries 17 computed-non-stored fields added by
`southbrook_project_mrp/models/project_project.py`. All are summed
or counted across the project's tasks that have linked MOs
(`production_count > 0`).

| Field                                       | Type     | What it counts                                          |
|---------------------------------------------|----------|---------------------------------------------------------|
| `southbrook_job_count`                      | Integer  | Tasks with ≥1 linked MO                                 |
| `southbrook_active_mo_count`                | Integer  | Sum of `production_count` across those tasks            |
| `southbrook_ready_job_count`                | Integer  | Tasks where all of: components ready, not at risk, no material risk, no equipment block |
| `southbrook_blocked_job_count`              | Integer  | Tasks where `manufacturing_readiness_state == 'blocked'` |
| `southbrook_review_job_count`               | Integer  | Tasks where `manufacturing_readiness_state == 'review'`  |
| `southbrook_at_risk_job_count`              | Integer  | Tasks where `job_at_risk == True`                       |
| `southbrook_material_risk_count`            | Integer  | Tasks where `material_at_risk == True`                  |
| `southbrook_cad_cutlist_job_count`          | Integer  | Tasks where `cad_cutlist_review_required == True`       |
| `southbrook_unscheduled_wo_count`           | Integer  | Σ `unscheduled_workorder_count` across tasks            |
| `southbrook_unscheduled_job_count`          | Integer  | Tasks with ≥1 unscheduled WO                            |
| `southbrook_can_start_today_wo_count`       | Integer  | WOs where `southbrook_can_start_today == True`          |
| `southbrook_crew_gap_count`                 | Integer  | Tasks where `crew_gap == True`                          |
| `southbrook_install_risk_job_count`         | Integer  | Tasks where `install_date_missing == True`              |
| `southbrook_equipment_blocked_count`        | Integer  | Tasks where `equipment_blocked == True`                 |
| `southbrook_over_capacity_count`            | Integer  | Tasks where `workcenter_over_capacity == True`          |
| `southbrook_job_cost_total`                 | Monetary | Σ `job_industrial_cost` across tasks                    |
| `southbrook_intelligence_prompt` + `_severity` | Char + Selection | The "Stop / Review / Clear" mission prompt the kanban tile renders |

All computed by `_compute_southbrook_mission_control` which is
`@api.depends` on the underlying task fields — recomputes on read
when any dependency changes.

### The mission prompt logic

`_southbrook_pick_mission_prompt` returns a `(severity, prompt)`
tuple based on first-match priority:

```
no jobs                            → "neutral", "No manufacturing jobs yet"
equipment_blocked > 0              → "danger",  "Stop: equipment blocked on N job(s)"
material_risk > 0                  → "danger",  "Stop: material shortfall on N job(s)"
at_risk_job_count > 0              → "warning", "Review: N job(s) at risk"
unscheduled_wo_count > 0           → "warning", "Review: N WO(s) need planned start"
crew_gap_count > 0                 → "warning", "Review: crew gap on N job(s)"
over_capacity_count > 0            → "warning", "Review: work-center load over capacity on N job(s)"
otherwise                          → "success", "Clear: material, crew, and equipment ready"
```

So the *first* triggered condition wins. If you have material risk
AND a crew gap, the prompt reads "Stop: material shortfall" — the
crew gap isn't surfaced in the prompt (it's still in the
`southbrook_crew_gap_count` badge, just not headline).

### The drill-down actions

12 action methods on `project.project`, each opening a filtered
view of `project.task` (or `mrp.workorder` for the WO-level ones):

| Method                                                | What it opens                                            |
|-------------------------------------------------------|----------------------------------------------------------|
| `action_southbrook_open_manufacturing_jobs`           | All tasks with ≥1 MO                                     |
| `action_southbrook_open_blocked_manufacturing_jobs`   | Tasks where state = blocked                              |
| `action_southbrook_open_review_manufacturing_jobs`    | Tasks where state = review                               |
| `action_southbrook_open_ready_manufacturing_jobs`     | Tasks where state = ready                                |
| `action_southbrook_open_unscheduled_manufacturing_jobs` | Tasks with unscheduled WOs                             |
| `action_southbrook_open_workorders_can_start_today`   | WOs flagged `southbrook_can_start_today`                 |
| `action_southbrook_open_cad_cutlist_jobs`             | Tasks where cad_cutlist_review_required                  |
| `action_southbrook_open_crew_gap_jobs`                | Tasks with crew_gap                                      |
| `action_southbrook_open_install_risk_jobs`            | Tasks with install_date_missing                          |
| `action_southbrook_open_equipment_blocked_jobs`       | Tasks with equipment_blocked                             |
| `action_southbrook_open_over_capacity_jobs`           | Tasks with workcenter_over_capacity                      |
| `action_southbrook_open_material_risk_jobs`           | Tasks with material_at_risk                              |

Plus 5 *persona-targeted* drill-downs that combine filters for a
specific role:

| Method                                                | Audience                                                  |
|-------------------------------------------------------|-----------------------------------------------------------|
| `action_southbrook_open_pm_control_queue`             | PM — all manufacturing jobs grouped by readiness          |
| `action_southbrook_open_shop_lead_queue`              | Shop lead — WOs that can start today                     |
| `action_southbrook_open_designer_queue`               | Designer / Engineer — needs CAD/cutlist OR missing specs |
| `action_southbrook_open_installer_queue`              | Install Coordinator — missing install date OR install readiness review |
| `action_southbrook_open_executive_queue`              | Executive — tasks at risk_level critical/high/medium      |

These are the buttons on the project form that drive the day's work
allocation: "Designer, here's your queue; Installer, here's yours."

### The Data Quality Dry Run

`action_southbrook_data_quality_dry_run` creates a
`southbrook.project.data.quality.report` record and populates it
with `southbrook.project.data.quality.line` rows for each issue
found. **It doesn't change any production data** — it's a read-only
audit.

Issues it flags:

| Issue Key                  | Severity | Trigger                                                                                |
|----------------------------|----------|----------------------------------------------------------------------------------------|
| `blank_kitchen_project`    | warning  | Non-done MO with no `project_task_id`                                                  |
| `missing_install_due`      | warning  | Task with linked MOs but no `job_install_due`                                          |
| `placeholder_estimated_cost`| info    | Task where `job_estimated_cost == 0`                                                   |
| `queue_overlap`            | blocker  | Task in state "ready" but `job_at_risk` OR `material_at_risk` OR `equipment_blocked` is also True |
| `equipment_count_mismatch` | warning  | `equipment_blocked != bool(maintenance_request_count)`                                 |
| `demo_scrap_unbuild`       | info     | Scrap or unbuild with "REF" in display name (looks like demo data)                     |

The report opens after creation and shows the issues list with
recommended actions. Use this:
- Weekly — to catch silent data drift before it builds up.
- After a major data migration or import — to validate the import.
- Before a board / leadership demo — to make sure dashboards are
  truthful.

### What counts as "late"?

There are two answers:

1. **At-risk task** (`job_at_risk == True`) — at least one non-done
   MO has `date_deadline.date() < today`, OR a started MO isn't
   fully reserved. The `job_risk_reason` Char enumerates the
   conditions. This is what the "X jobs at risk" mission prompt
   counts.

2. **Install-risk task** (`install_date_missing == True`) — the
   task has linked MOs but `job_install_due` is null. Not "late"
   strictly — it's "can't tell if it's late because the date is
   missing." Surfaced separately because the resolution is
   different (chase the install date from the customer, not the
   shop floor).

There's **no explicit "completed late" metric** in the project
rollup — for that, query MO `date_finished > date_deadline` in
Manufacturing.

## Your daily flow

**Monday morning (10 min): the leadership update**

1. Open **/odoo/project**.
2. If you've activated the mission-control kanban (lesson 14.6),
   eyeball the mission prompt on each project tile. Green = nothing
   to escalate. Yellow / red = drill in.
3. Click the relevant project to open its form.
4. Read the smart buttons: # Customer Jobs, # Ready, # Blocked,
   # At Risk.
5. The numbers ARE your slide. Snapshot them; you're done.

**Weekly (30 min): the trend deep-dive**

The rollup fields are computed-non-stored — they don't have a
historical trend on their own. For trends:

1. Open **/odoo/project → project → Action → Southbrook Data
   Quality Dry Run** (creates a report).
2. Compare to last week's report (open from Settings → Technical
   → Database Structure → Data Quality Reports).
3. Look at the issue counts week-over-week — are
   `blank_kitchen_project` warnings growing? That means MOs are
   being created without auto-linking (lesson 14.5 covers the
   repair).

For deeper trend analysis, you need to export the underlying task
data and chart it externally:

1. Open the task list (any filter).
2. Top-right kebab → *Export All* (developer mode) or *Export
   selected* (any user).
3. Pick fields: `date_deadline`, `stage_id`, `production_count`,
   `job_at_risk`, `job_install_due`, `southbrook_production_release_state`,
   `manufacturing_readiness_score`.
4. Download as XLSX or CSV → chart in Excel / Google Sheets.

**Daily (5 min): the late-task chase**

1. Open the project form → click **At-Risk Jobs** drill-down.
2. The list opens filtered to `job_at_risk = True`.
3. Sort by `install_due_date` ascending.
4. For each, read `job_risk_reason` (one of:
   "N MO(s) waiting on components", "N MO(s) past deadline").
5. Chase the reason — components → procurement; past deadline →
   reschedule.

**Persona drill-downs (Designer / Installer / Shop Lead):**

These five actions are the right way to delegate work. Open the
project, click the persona button, and the user gets the filtered
view to work through. The actions also drop the right
`search_default_*` context so the user lands with the relevant
filters already applied.

## Common mistakes + how to recover

**"The mission prompt says 'Clear: material, crew, and equipment
ready' but I know there's a late job."**

The mission prompt is a *first-match* lookup that doesn't include
`at_risk_job_count` past the equipment + material checks unless
those are zero. Wait — actually it DOES check at_risk_job_count
third. If it's saying "Clear", then `at_risk_job_count == 0`. The
job you think is late might not be `job_at_risk = True` (e.g. the
MO `date_deadline` is null, so the past-deadline check can't
trigger). Open the task and check the MO's deadline field.

**"The rollup shows 4 'Ready' jobs but only 3 are actually ready."**

The "ready" rollup is computed as:
```
components_available == 'ready' AND not job_at_risk
AND not material_at_risk AND not equipment_blocked
```
Note it does NOT check `southbrook_production_release_state`. So a
task whose components are reserved, no risk flags raised, but
release checklist still has incomplete sign-offs counts as "ready"
in *this* rollup. The "blocked" / "review" rollup reads from
`manufacturing_readiness_state` which DOES include release
checklist — and that's the authoritative one. The "ready" rollup
is a quick-glance proxy, not authoritative.

**TBD:** consider tightening `southbrook_ready_job_count` to also
require `manufacturing_readiness_state == 'ready'` so the two
counts can't disagree. Currently they can.

**"The Data Quality Dry Run flagged 50 `demo_scrap_unbuild` issues
on a fresh install."**

The check matches any scrap or unbuild with "REF" in the display
name. Native Odoo demo data uses "REF" as a SKU prefix. On a fresh
install with demo data loaded, these will fire heavily. Mitigation:
either delete the demo data (Settings → Technical → Demo Data) or
set `southbrook_exclude_from_pm_reports` to True on the
scrap/unbuild records you want to keep (the check honors that flag).

**"The drill-down opens an empty list."**

The action methods use `.filtered()` against the in-memory
recordset, not a SQL domain. If the filter condition uses a
computed-non-stored field, the filter still works — but you can't
sort/paginate efficiently and the URL doesn't carry the filter, so
refreshing reverts. For large databases (>5K tasks), this is slow.
Workaround: use the search view's quick filters instead, which are
domain-based.

**"I want to schedule a weekly report email."**

Native Odoo's scheduled-action + email-template machinery works,
but you'll need to author the QWeb template and the cron yourself
— there's no canned weekly report in the addon. **TBD:** consider
adding `southbrook.project.data.quality.report.email_weekly` cron
in a future release.

**"The 'Can Start Today' WO count is 0 but I have WOs scheduled
for today."**

`southbrook_can_start_today` is a Boolean on `mrp.workorder`
computed by `southbrook_kitchen_workspace` (or a related addon —
TBD which exactly). It requires more than a `date_start = today`
check: it usually also requires preceding WOs done, components
reserved, workcenter free. If those aren't true, the count is 0.
Open Manufacturing → Work Orders and filter to today's date_start
to see the full list; `Can Start Today` is the subset that's
*actually* ready.

## What the system is doing behind the scenes

The project-level rollups are **pure aggregations** over the task
set: `for task in tasks` walks. There's no caching, no
materialised view, no batch job. Every read of the rollup field
re-walks the task set. For projects with ≤1000 tasks this is
fast (<100 ms); for >5000 tasks the rollup is the slowest field
on the project form and may trip the readiness view's <2s
expectations.

The mission-control kanban is shipped *inactive* (lesson 14.6) in
part because the rollup costs add ~200 ms per project tile, which
multiplies on a 50-project list view. Activate it for production
managers; don't activate it globally.

The 12 drill-down actions use `.filtered()` rather than domain-
based searches because most of the filter fields are computed-
non-stored. The cost is:
- Loading every task in the project into memory.
- Filtering in Python.
- Returning ids to the act_window.

For a project with 200 active tasks this is ~50 ms — fine. For one
with 5000+ archived tasks (an old "catch-all" project), it can be
slow.

The Data Quality Report is **idempotent and additive**: each call
to `action_southbrook_data_quality_dry_run` creates a new
`southbrook.project.data.quality.report` record with a fresh
timestamp. Old reports stay. This is by design — the historical
trail IS the trend. Don't auto-delete old reports; archive them if
they're cluttering the list.

The persona-targeted queues
(`action_southbrook_open_pm_control_queue` et al.) set
`search_default_*` context keys to pre-apply search filters on the
opened view. This lets one user "pin" a persona view as their
homepage by saving the filter combination as a favorite. The list
view's default ordering is by `install_due_date` ascending, so the
most urgent jobs surface first.

## Quiz (5 questions, applied)

**1.** The mission prompt on a project tile says "Stop: equipment
blocked on 2 job(s)." You drill in — only 1 job has
`equipment_blocked = True`. Bug?

> Likely a stale read on the kanban tile vs. fresh compute on
> drill-down. The rollup `southbrook_equipment_blocked_count` is
> computed-non-stored; the kanban tile read may be cached from a
> previous compute. Refresh the kanban (browser reload) and the
> number will reconcile to 1. The drill-down is authoritative — it
> uses `.filtered()` over the live recordset.

**2.** Leadership asks "how many jobs did we ship last week?" The
project rollups don't tell you. Where do you go?

> The project rollups are point-in-time, not historical. Go to
> Manufacturing → Operations → Manufacturing Orders. Filter:
> `state = done` AND `date_finished within last 7 days`. Group by
> Customer Job (`project_task_id`). Count distinct task IDs —
> that's "jobs shipped last week" (where a job is the customer
> kitchen, not a single MO).

**3.** The Data Quality Dry Run reports 12
`blank_kitchen_project` warnings. What do you do?

> Open the report. Each line names a specific `mrp.production`
> record with no `project_task_id`. For each: open the MO, look at
> the SO line, find the right task (via the SO's
> `x_southbrook_sale_order_id` link from the task side), and either
> (a) run `Link MOs from Sale` on that task (faster, 1-click), or
> (b) set `project_task_id` manually on the MO. Lesson 14.5 has the
> orphan-repair flow in detail.

**4.** You want to schedule a weekly Data Quality Dry Run that
emails the result to the production manager. Tell me the high-
level approach.

> (a) Create an `ir.cron` (in your own addon — not in
> `southbrook_project_mrp`) that calls
> `env['project.project'].search([]).action_southbrook_data_quality_dry_run()`
> weekly. (b) Override the action to also send an email after
> creating the report — use `mail.template` + `template.send_mail(report.id)`.
> (c) Author the email template with QWeb to render the line list.
> (d) Test with `--test-enable`. Don't touch the existing
> `southbrook_project_mrp` addon — extend it from a side module so
> upgrades stay clean.

**5.** The PM Control Queue button on the project form opens an
empty list, but the project has 50 active tasks. Why?

> The PM Control Queue filters to `production_count > 0` AND
> opens with `search_default_manufacturing_blocked: 1`. If none of
> the 50 tasks have linked MOs (e.g. SOs not yet confirmed), the
> list is empty. Resolution: the manufacturing pipeline hasn't
> started — that's correct behavior. To see all 50 tasks, use the
> stock "Tasks" smart button on the project, not the PM Control
> Queue.

---

## What this lesson does NOT cover

- The 17 rollup field internals at line-by-line code level — see
  `southbrook_project_mrp/models/project_project.py`.
- Manufacturing-side reporting (OEE, cycle time, workcenter
  utilisation) → Course 2 lesson 2.5 + Course 3 lesson 3.3.
- The Kitchen Ops report grid (Kitchen Jobs board + filter
  dashboard) → Course 12 lesson 12.6.
- Building custom QWeb reports for project-level PDFs → Course 8
  lesson 8.1 (`08_custom_reports.md`).
- The Hermes Console queues that consume the same rollup data →
  Course 7 lesson 7.3.
- Native Odoo's Tasks Analysis + Burndown reports — those read
  stock fields (`open_task_count`, etc.), not Southbrook ones.
  Stock reports are not extended by `southbrook_project*`.
