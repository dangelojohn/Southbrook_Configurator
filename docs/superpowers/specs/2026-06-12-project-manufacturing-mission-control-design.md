# Project Manufacturing Mission Control Design

## Goal

Transform `/odoo/project` from a generic Odoo project card grid into a manufacturing-relevant command page for Southbrook Cabinetry. The page should help production managers, cabinet makers, cutters, operators, and installers see which jobs can move, which jobs are blocked, and which mistakes need attention before work reaches saw, CNC, edgebander, assembly, finishing, delivery, or install.

The Project layer remains an orchestration layer above Odoo MRP. It must surface existing Project, MRP, Work Order, Inventory, Purchase, and Maintenance facts. It must not rebuild BoM logic, routing, costing, scheduling, ECO, purchasing, or security.

## Product Principle

Use the Project module as a manufacturing control surface:

- Can we build it?
- Should we build it now?
- What mistake are we about to make?

The page should favor practical intelligence prompts over abstract reporting. A project card should behave like a compact job command card, not a generic task counter.

## Recommended Approach

Implement a Project Overview Kanban enhancement on `project.project`.

Each project card will summarize manufacturing readiness across its tasks and linked MOs/WOs. A compact top-level summary band may be added if Odoo's inherited Project view provides a stable insertion point. If not, the first implementation should prioritize richer project cards, because cards are the primary object visible at `/odoo/project`.

This is preferred over a separate dashboard because it preserves the user's existing entry point and avoids creating a parallel workflow. It is also preferred over a full custom frontend because Odoo's access rules, menus, actions, and native drill-downs remain intact.

## Data Sources

Use only existing model facts and fields already computed by Southbrook modules:

- `project.project`
- `project.task`
- `project.task.production_ids`
- `mrp.production`
- `mrp.workorder`
- `purchase.order` links already exposed through `southbrook_project_mrp`
- `maintenance.request` links already exposed through `southbrook_project_mrp`
- Manufacturing intelligence counts already exposed by `southbrook_manufacturing_intelligence` where available

The first implementation should aggregate from project tasks. Task-level fields already available include:

- `production_count`
- `job_at_risk`
- `job_risk_reason`
- `components_available`
- `workorder_count`
- `unscheduled_workorder_count`
- `crew_gap`
- `unassigned_workorder_count`
- `job_industrial_cost`
- `job_variance_min`
- `job_cost_variance`
- `material_at_risk`
- `material_ready_count`
- `material_partial_count`
- `material_unavailable_count`
- `procurement_count`
- `equipment_blocked`
- `maintenance_request_count`
- `workcenter_over_capacity`

## Project Card UX

Each Project Kanban card should show:

- Project name.
- Current job/task count.
- Manufacturing readiness chips:
  - Ready to build.
  - At risk.
  - Material shortfall.
  - Needs scheduling.
  - Crew gap.
  - Equipment blocked.
  - Over capacity.
- A short intelligence prompt derived from the highest-priority condition.
- One primary action that opens the project task board or production board.

Severity language:

- Red: work should not proceed.
- Amber: lead hand or production manager should review.
- Blue/gray: efficiency prompt.
- Green: clear/ready.

Example prompts:

- `Stop: equipment blocked on 1 work center`
- `Review: 47 WOs need planned start`
- `Review: crew gap on 47 WOs`
- `Clear: material ready across linked MOs`
- `Cost check: $674.42 planned MO cost`

## Aggregation Rules

Add read-only computed fields to `project.project` in the Southbrook Project/MRP layer or a small companion module:

- `southbrook_job_count`
- `southbrook_active_mo_count`
- `southbrook_ready_job_count`
- `southbrook_at_risk_job_count`
- `southbrook_material_risk_count`
- `southbrook_unscheduled_wo_count`
- `southbrook_crew_gap_count`
- `southbrook_equipment_blocked_count`
- `southbrook_over_capacity_count`
- `southbrook_job_cost_total`
- `southbrook_intelligence_prompt`
- `southbrook_intelligence_severity`

The compute should summarize related tasks for the project. It should not search globally without a project constraint. It should degrade to zeros and neutral text when no manufacturing-linked tasks exist.

## Navigation

Project cards should retain native Odoo behavior. Add only native actions:

- Open project tasks filtered to that project.
- Optional smart action to open manufacturing-linked tasks for that project.

Do not add external links, custom security, or account/user changes.

## Error Handling

Computed fields must be null-safe:

- Empty projects return zero counts.
- Tasks without MOs return neutral counts.
- Missing optional intelligence fields are handled with `getattr`.
- Date/datetime comparisons must be type-aligned.
- Views must never reference fields not defined on the target model.

## Testing

Automated tests should cover:

- Project with no manufacturing tasks.
- Project with task #182-style linked MOs and WOs.
- Aggregation of unscheduled WOs.
- Aggregation of material readiness.
- Aggregation of equipment blocked.
- Highest-priority prompt selection.
- Project Kanban view loads with all referenced fields.

Live verification should include:

- Open `/odoo/project`.
- Confirm the `Test` project card renders without RPC error.
- Confirm the card shows manufacturing counts derived from task #182.
- Open the project/task board from the card.
- Confirm task #182 still opens.

## Out Of Scope

- Finite-capacity scheduling.
- Gantt replacement.
- Drag/drop production planning.
- BoM, routing, costing, ECO, or procurement engines.
- Security/share/follower/access changes.
- User creation or credential changes.

## Rollout Plan

1. Add project-level computed manufacturing summary fields.
2. Add focused tests for project-level aggregation and view loading.
3. Enhance the Project Kanban card with readiness chips and the intelligence prompt.
4. Upgrade locally and run focused tests.
5. Deploy to QNAP.
6. Verify `/odoo/project`, the Test project card, and task #182 live.

