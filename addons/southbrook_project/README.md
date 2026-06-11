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

## Install

```bash
odoo -d <db> -i southbrook_project
```

Depends only on `project` (already installed on every Southbrook
Odoo). No other prerequisites.

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

This commit ships no automated tests — the work is configuration +
view inheritance, both verified by:

* `odoo -i southbrook_project -d <db> --stop-after-init` (clean
  install with no ParseError).
* Manual confirmation on the live instance that:
  - All 5 stages still render in Kanban at 1280 px width.
  - The 6 tags appear in the tag picker.
  - Project 1's description / dates / dependencies / milestones
    fields are populated.
  - A new task shows the Cabinetry Specs tab + priority badge.

## License

LGPL-3.0.
