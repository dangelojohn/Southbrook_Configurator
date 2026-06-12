# Southbrook Project

Cabinetry-shop polish on the stock Odoo 19 Project module, targeting
the findings from the manual QA pass against the live
`southbrookcabinetry.space` Project instance.

## What ships

### Tier 1 — Responsive Kanban

`static/src/scss/kanban_responsive.scss`

* Desktop (>=1280 px): all 5 stage columns render side-by-side; the
  Kanban renderer no longer horizontal-scrolls when the columns fit
  naturally. Columns flex-share available width (`flex: 1 1 0`)
  capped at 380 px so an empty board doesn't get hilariously wide.
* Tablet (480–1279 px): preserves horizontal scroll but bumps the
  column min-width so at least 1.5 columns are visible at the
  starting position.
* Phone (<480 px): full-viewport-width single column; preserves
  swipe-to-next behaviour.
* Scoped to `.o_kanban_view.o_kanban_project_task` and
  `[data-model="project.task"]` so other models' kanbans are
  untouched.

### Tier 2 — Tags + Project 1 defaults

`data/project_tags.xml` — seeds the 6 tags the QA report named:

| Tag | Color | Purpose |
|---|---|---|
| Rush | 1 (red) | Ship ahead of normal SLA |
| Custom | 2 (orange) | Non-stock cabinet sizing / hardware |
| Warranty | 3 (yellow) | Existing warranty coverage |
| Repair | 4 (light green) | Service call, not new manufacture |
| Kitchen | 5 (dark blue) | Kitchen scope |
| Vanity | 6 (light purple) | Bathroom vanity scope |

`data/project_1_defaults.xml` — populates the blank fields on
project ID 1 (`Test`):

* `description` — paragraph explaining the 5-stage pipeline +
  tagging convention.
* `date_start` — set to install date.
* `date` (planned end) — install date + 6 months.
* `allow_task_dependencies` = True (Tier 3).
* `allow_milestones` = True (Tier 3).

Stages were already seeded by an earlier pass (Design & Quote →
Cutting & Machining → Assembly → Finishing → Delivery & Install).

### Tier 3 — Feature flags

Enabled via the project 1 record write above:

* `allow_task_dependencies` — predecessor / successor links between
  production steps.
* `allow_milestones` — explicit production milestones (Quote
  Approved, Cut Complete, Assembled, Sprayed, Delivered).

Left as operator toggles in Settings:

* `allow_recurring_tasks` — only useful if the shop has standing
  recurring jobs (e.g. monthly catalog refresh).
* `allow_billable` — only useful when labor is invoiced separately
  (commonly when the shop sub-contracts install).

### Tier 4 — Cabinetry custom fields + subtask count + priority

`models/project_task.py`:

* `x_southbrook_material_species` — 12-option Selection (Maple,
  Red/White Oak, Cherry, Walnut, Hickory, MDF Painted, White /
  Woodgrain Melamine, White Thermofoil, Birch Plywood, Other).
* `x_southbrook_unit_count` — Integer (number of cabinet units this
  task represents).
* `x_southbrook_hardware_specs` — Text (hinge / handle / drawer-
  slide free-text until the hardware catalog picker lands).
* `x_southbrook_sale_order_id` — Many2one(sale.order, ondelete=
  set null), click-through to the originating quote.
* `x_southbrook_priority` — Selection(Standard / Rush / Urgent),
  clearer than stock's single-star toggle that logged "Medium
  priority". Stock priority is left intact for integration parity.
* `display_name` override — suffixes the SO ref when present so the
  Kanban card surfaces it at a glance.

`models/project_task.py` (project.project extension):

* `southbrook_top_level_task_count` — sums only tasks with
  `parent_id IS NULL`, not subtasks. The QA report flagged that a
  job with 3 production sub-steps showed as "4 Tasks" in the project
  overview because subtasks counted as full tasks. Operators read
  this field instead of `open_task_count` to see real job count.

`views/project_task_views.xml`:

* Form view: new "Cabinetry Specs" notebook tab (after Description)
  with the 4 custom fields. Header bar gets the Southbrook priority
  badge.
* List view: priority badge + material + unit count + SO link as
  optional columns.
* Search view: Rush / Urgent quick filters, search by SO + material,
  group-by priority + material.

### Kitchen Job Command Center

`models/manufacturing_command.py` and `models/job_command.py` turn
Project into the PM command surface while MRP remains the backend
system of record.

* Readiness snapshots: stored score, state, blocking gate, blocker
  summary, next action, and gate JSON so queues can search/group
  reliably.
* Release gate: `Release to Production` recomputes readiness and
  blocks if required materials, checklist, tooling, MRP, or MI gates
  are not ready.
* Job templates: Kitchen, Vanity, Repair, and Warranty templates seed
  structured specs and release checklist items.
* Checklist readiness: unchecked required checklist items block the
  mapped readiness gate; optional unchecked items warn.
* Cabinet specs: job type, cabinet family, material/species, unit
  count, hardware specs, install due, and spec summary are visible on
  the task form and command queues.
* Cabinet-family drilldown: the task header opens the existing
  `southbrook.cabinet.family` progress surface.

PM menu entries under `Southbrook PM`:

* Job Templates
* Daily Production Meeting
* Blocked Jobs
* Ready to Release
* At-Risk Jobs
* Data Quality Dry Run

### Rollout Data Quality

`models/data_quality.py` provides a dry-run report for rollout
cleanup. It creates issue records only; it does not delete or mutate
the source production records.

The report flags:

* blank Kitchen Project
* blank Install Due
* placeholder Southbrook product costs
* demo scrap/unbuild records
* queue overlap
* equipment count mismatches

Safe actions on the issue record:

* `Exclude from PM Reporting` marks the issue excluded.
* `Archive Issue` archives the issue record.

Pilot documentation for `S00235` lives at:

* `docs/SOUTHBROOK_PROJECT_ROLLOUT_PILOT.md`

## Install

```bash
odoo -d <db> -i southbrook_project
```

This addon now spans the project command-center surface and the MRP
readiness read model. It depends on Project, Sales, Purchasing, MRP,
Maintenance, the shop-floor MRP modules, kitchen tooling, kitchen
production packages, and Manufacturing Intelligence:

* `project`
* `sale_management`
* `purchase`
* `mrp`
* `maintenance`
* `southbrook_mrp_pm`
* `southbrook_mrp_kitchen_tools`
* `southbrook_kitchen_mrp`
* `southbrook_manufacturing_intelligence`

## What was deliberately deferred to a human

* **User accounts.** Tier 2.2 asked for real shop staff as
  assignable users. Per Guardrails, no credentials are entered and
  no users are created. The operator should add staff under
  Settings → Users & Companies → Users.
* **Permission / share / follower changes.** Per Guardrails, no
  ACL touched.
* **`hr_timesheet` install.** Tier 4.3 asked for timesheets so the
  Tasks Analysis + Burndown reports become meaningful. Installing
  `hr_timesheet` adds 4 models (account.analytic.line extension,
  hr_timesheet wizard, project_timesheet_holidays) and changes
  several views; the QA pass should review whether timesheet entry
  is appropriate for the shop floor (the existing tool consumption
  log already covers tool-side time, just not operator labor time).
  The flip is one toggle in Apps if the operator decides to proceed.
* **`allow_billable`.** Only useful when labor is invoiced
  separately. The operator should evaluate after deciding on
  timesheets.

## Tests

The responsive Project configuration and view inheritance are verified
by:

* `odoo -i southbrook_project -d <db> --stop-after-init` (clean
  install with no ParseError).
* Manual confirmation on the live instance that:
  - All 5 stages still render in Kanban at 1280 px width.
  - The 6 tags appear in the tag picker.
  - Project 1's description / dates / dependencies / milestones
    fields are populated.
  - A new task shows the Cabinetry Specs tab + priority badge.

The MRP command center readiness scoring and gate aggregation tests
are intentionally exposed as a focused target because the full
repository test sweep does not cold-install `southbrook_project` and
its MI/tooling dependencies:

```bash
make test-mrp-command
```

That target upgrades `southbrook_project` and runs only
`mrp_command/southbrook_project` against the configured Docker Odoo
database.

## License

LGPL-3.0.
