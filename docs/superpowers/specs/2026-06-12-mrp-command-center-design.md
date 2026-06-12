# Southbrook MRP Command Center MVP

## Purpose

Build the first project-level manufacturing scheduling orchestration surface for
Southbrook Cabinetry. The system should help a senior MRP project manager decide
whether a kitchen job can safely proceed through the waterfall production flow,
and if not, show the exact blockers that must be cleared before release.

The first release focuses on readiness, gating, exception visibility, and
standard Odoo views. It does not attempt a full drag/drop finite scheduler yet.

## Success Criteria

- A project/job answers: "Can this be released to production?"
- If release is blocked, the user sees a concise blocker summary.
- Readiness covers engineering, BOM/cutlist, materials, purchasing, tooling,
  labor, equipment, production schedule, delivery, and install readiness.
- Release to production blocks when required gates fail.
- Purchasing, engineering, tooling, labor, equipment, and install exceptions
  are visible in actionable queues.
- The PM can run a daily production meeting from one dashboard using standard
  Odoo views.
- Existing Southbrook modules remain the source of truth for their domains.

## Recommended Approach

Extend the existing modules instead of creating a separate orchestration addon
in this first pass:

- `southbrook_project` owns project/task job context and the project-level
  command panel.
- `southbrook_mrp_pm` owns work-center, work-order, capacity, and floor-manager
  surfaces.
- `southbrook_mrp_kitchen_tools` owns tooling readiness.
- `southbrook_manufacturing_intelligence` owns production/package checks and
  stage-gate intelligence.
- `southbrook_kitchen_mrp` owns production packages, cutlists, and hardware
  packages.

This approach is fastest because the repo already has stage-aware MI checks,
tool readiness, work-center KPIs, capacity pivots, and project task extensions.
If orchestration grows beyond these modules, a later
`southbrook_mrp_orchestration` addon can consolidate cross-module logic.

## Waterfall Gates

The MVP gate sequence is:

1. Estimate
2. Engineering
3. BOM / Cutlist
4. Purchasing
5. Materials
6. Tooling
7. Labor
8. Equipment
9. Production Schedule
10. Delivery
11. Install

Each gate has:

- `state`: `not_started`, `ready`, `warning`, `blocked`, or `waived`
- `severity`: highest active issue severity
- `owner`: purchasing, engineering, production, tooling, maintenance, install,
  or PM
- `message`: short human-readable status
- `action`: next step required to clear the gate
- `blocking`: boolean used by release enforcement

The MVP can implement gates as computed fields and helper methods on
`project.task` rather than a new persistent gate model. A persistent model is
only justified once gate history, manual signoff audit, or configurable gate
templates become required.

## Readiness Score

Add a project/job readiness score from 0 to 100 on `project.task`.

Scoring should be deterministic and explainable:

- Any blocking gate caps the score at 69.
- Any warning gate caps the score at 89.
- A fully ready job scores 100.
- Missing noncritical data lowers the score but does not block release.

Suggested starting weights:

- Engineering and drawings: 10
- BOM/cutlist: 12
- Purchasing/materials: 18
- Tooling: 12
- Labor: 10
- Equipment: 10
- Production schedule: 12
- Delivery/install readiness: 10
- Data completeness: 6

Fields:

- `x_southbrook_readiness_score`
- `x_southbrook_readiness_state`: `ready`, `at_risk`, `blocked`
- `x_southbrook_blocker_summary`
- `x_southbrook_next_action`
- `x_southbrook_blocking_gate`

## Release Gate Behavior

Add a PM-facing action named `Release to Production` on the job/task command
panel.

The action must:

1. Recompute project readiness.
2. Recompute related manufacturing intelligence checks where production
   packages or MOs exist.
3. Recompute tool readiness for related work orders where available.
4. Fail with a `UserError` when any required gate is blocked.
5. Include the first three blocker reasons in the error message.
6. Proceed to existing send-to-production behavior only when gates pass.

The user should not have to inspect five modules to understand the failure.
The error message should read like:

> Cannot release SO24091. CNC tooling is blocked, edge band PO 00452 is late,
> and engineering drawing revision C is not approved.

## Exception Queues

Add standard Odoo list/search/kanban actions for:

- Purchasing exceptions
- Engineering exceptions
- Tooling gaps
- Labor gaps
- Equipment alerts
- Install readiness
- Blocked jobs
- Jobs ready for release

The MVP can implement these as filtered actions over existing models where
possible:

- `project.task` for job-level readiness and blocker queues.
- `southbrook.mi.check` for production intelligence blockers.
- `mrp.workorder` for schedule/tooling/labor readiness.
- `maintenance.equipment` for equipment condition alerts.
- `purchase.order` or purchase lines for late purchasing exceptions when linked
  to jobs or sale order origins.

If a domain cannot be reliably linked in the MVP, surface it as a warning with
an explicit "link missing" message rather than hiding it.

## Project Command Panel UX

The Project task form should gain a "Manufacturing Command" page or top-level
smart panel.

It should show:

- Readiness badge: `Ready`, `At Risk`, or `Blocked`
- Numeric readiness score
- Blocker summary
- Next required action
- Waterfall gate checklist
- Related sale order
- Related manufacturing orders
- Related production packages
- Related work orders
- Material/purchasing status
- Tooling status
- Equipment status
- Labor/schedule status
- Install readiness status
- Action buttons for release, request purchasing action, assign crew, and
  reschedule

Use Odoo-native widgets first:

- Badge widgets for state and severity.
- Stat buttons for related documents.
- Notebook page for detailed readiness.
- List views for related blockers.
- Kanban/list/pivot for dashboards.

Custom JavaScript is out of scope for the MVP.

## PM Dashboard UX

Add a daily production meeting action under the Southbrook PM menu.

The dashboard should include:

- Jobs blocked today
- Jobs ready for release
- Late or at-risk jobs
- Purchasing exceptions tied to planned starts
- Work-center load for the next five to seven shop days
- Tooling gaps
- Equipment alerts
- Install readiness exceptions

Use standard Odoo views:

- Kanban for job readiness cards.
- List for blockers and exception queues.
- Pivot/graph for work-center load.
- Search filters grouped by owner, gate, severity, work center, and planned
  start date.

The visual target is documented in:

`docs/superpowers/mockups/2026-06-12-mrp-command-center.html`

## Data Flow

1. Customer/dealer order produces sale order lines.
2. Existing send-to-production logic creates MOs and work orders.
3. Production packages, cutlists, hardware packages, and work orders provide
   manufacturing data.
4. Manufacturing Intelligence generates stage-aware checks.
5. Tool Control computes work-order tool readiness.
6. Equipment condition comes from `maintenance.equipment`.
7. Project task aggregates these signals into readiness fields.
8. Release action blocks or proceeds based on the aggregate state.
9. PM dashboard and exception queues read the same fields and checks.

The project/task aggregate is a read model. It should not duplicate the source
records that already exist in MRP, purchase, maintenance, tooling, or MI.

## Error Handling

- Missing related records should create warnings unless the gate depends on
  them. Example: no production package before release is a blocker; no install
  package six weeks before install may be a warning.
- A failed recompute in one domain should not prevent other checks from being
  shown. Capture the failure as a warning where possible.
- Release errors should be short and actionable.
- Detailed diagnostics should remain visible in the command panel.
- Waivers are out of scope for the first pass unless already supported by an
  existing model.

## Security

Use existing internal user groups where possible:

- PM / production manager can release and view all readiness.
- Floor manager can view production/tool/equipment blockers.
- Purchasing can view and clear purchasing exceptions.
- Engineering can view engineering/BOM exceptions.

Do not expose internal readiness dashboards to portal users in this MVP.

## Testing

Add focused Odoo tests for:

- Readiness score calculation with all gates ready.
- Blocked readiness when BOM/cutlist is missing.
- Blocked readiness when a mandatory tool requirement is unavailable.
- Warning readiness when equipment is in watch/fair condition.
- Release action raises `UserError` with clear blocker text.
- Release action proceeds when gates are ready.
- Project form/view loads with the command panel.
- PM dashboard actions and search views load.
- Exception queue domains return expected records.

Where full Odoo tests are too heavy for QNAP, run rollback-only `odoo shell`
assertions against the live container after module update.

## Phasing

### Phase 1: Readiness Read Model

- Add project/task readiness fields.
- Add helper methods to collect related MOs, packages, checks, work orders,
  tool readiness, equipment alerts, and purchasing exceptions.
- Add deterministic readiness calculation.

### Phase 2: Release Enforcement

- Add `Release to Production` action.
- Gate existing send-to-production behavior.
- Return concise blocker messages.

### Phase 3: Command Panel UX

- Add project task command page.
- Add readiness badges, gate checklist, blocker summary, related records, and
  PM actions.

### Phase 4: Exception Queues

- Add PM menu actions for blocked jobs, jobs ready for release, purchasing
  exceptions, tooling gaps, equipment alerts, and install readiness.

### Phase 5: Daily Production Meeting View

- Assemble existing work-center KPIs, capacity pivot, readiness queues, and MI
  blockers into a daily PM dashboard.

## Out of Scope

- Drag/drop finite-capacity scheduler.
- Custom OWL scheduling board.
- Barcode scanning workflow changes.
- Machine telemetry.
- Automatic purchase order creation.
- Automatic labor assignment optimization.
- Portal/customer-facing readiness views.
- Manual waiver/audit workflow unless required during implementation review.

These are follow-up candidates once the readiness and release-gate model is
trusted.
