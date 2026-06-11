# Southbrook Manufacturing Intelligence Stage Gates

## Purpose

Upgrade `southbrook_manufacturing_intelligence` from package-level checks into plant-manager production control. The addon should help junior operators and lead hands stop bad work before it reaches saw, CNC, edgebander, assembly, finishing, delivery, or install.

The design favors practical shop-floor calculations and stage readiness over abstract reporting. Checks must say what is wrong, why it matters, and what action is needed next.

## Operating Rules

- Use `blocker` when work must not proceed.
- Use `warning` when a lead hand or production manager must review.
- Use `info` for efficiency prompts, reminders, batching, labeling, staging, and offcut reuse.
- Each check should belong to a production stage so the manager can see where flow is blocked.
- Existing cut, hardware, assembly, handling, and install calculations remain valid and become stage-aware.

## Stages

The first stage set is intentionally close to the physical plant flow:

- `saw`: panel cutting, sheet fit, yield, batching, offcut labels.
- `cnc`: machining, drill readiness, grain/orientation, missing machine data.
- `edgeband`: edge-banding config, band length, missing/ambiguous edges.
- `assembly`: hardware package, shelves, handling, lift requirements.
- `finish_qc`: finish/QC review, fragile or high-risk items.
- `delivery`: route, staging, tall/heavy cabinet handling.
- `install`: filler, scribe, tip-up clearance, ceiling/path risks.

## Data Model

Extend `southbrook.mi.check` with:

- `stage`: selection field for the stages above.
- `workcenter_id`: optional `mrp.workcenter` link for machine/stage ownership.
- `sequence`: integer for production-flow ordering.
- `is_gate`: boolean to mark checks that control stage readiness.

Existing fields remain:

- `severity`
- `category`
- `message`
- `recommendation`
- `production_id`
- `production_package_id`

Add package rollup fields:

- `x_mi_blocked_stage`
- `x_mi_next_stage_action`
- `x_mi_saw_blocker_count`
- `x_mi_cnc_blocker_count`
- `x_mi_edgeband_blocker_count`
- `x_mi_assembly_blocker_count`
- `x_mi_finish_qc_blocker_count`
- `x_mi_delivery_blocker_count`
- `x_mi_install_blocker_count`

## Stage-Gate Rules

### Saw

Blockers:

- Missing cutlist.
- Oversized panel that cannot fit configured sheet dimensions.

Warnings:

- Low sheet yield.
- Grain panel only fits by rotation.

Info:

- Reusable offcut labeling.
- Batch cut duplicate panels.

### CNC

Blockers:

- Future machining/drilling data missing when the package requires CNC operations.

Warnings:

- Grain/orientation review before machining visible parts.
- Tall/large panel machining review when handling or vacuum hold-down may be risky.

### Edgeband

Blockers:

- Future explicit edge requirement exists but edge configuration is missing.

Warnings:

- High edge-band length package.
- Edge-band config is malformed or defaults to full perimeter because the JSON could not be parsed.

Info:

- Total edge-band meters for staging coil/material.

### Assembly

Blockers:

- Missing hardware package.
- Empty hardware pick list.
- Mechanical lift required.

Warnings:

- Hardware not picked.
- Hardware pricing pending.
- Long shelf support review.
- Two-person panel handling.

### Finish / QC

Warnings:

- Large or heavy visible panels require QC/handling plan.
- Future finish-sensitive substrates or visible doors require extra inspection.

### Delivery

Warnings:

- Tall/heavy package needs route and staging review.
- Future delivery dimensions exceed normal handling thresholds.

### Install

Warnings:

- Tall cabinet install review.
- Tip-up clearance review.

Info:

- Filler and scribe confirmation.

## Manager Dashboard

Add a plant-manager action under the relevant Southbrook manufacturing menu. It should provide:

- A list/pivot-style check view grouped by `stage` and `severity`.
- Filters for `Blockers`, `Warnings`, `Gate Checks`, and each stage.
- Package list showing status, blocked stage, blocker count, warning count, and next stage action.
- Existing PM kanban MI chips continue to show workcenter blocker/warning pressure.

The first dashboard should use standard Odoo list/search/kanban patterns rather than custom JavaScript. This keeps it maintainable and deployable on the current QNAP environment.

## Engine Architecture

Refactor `southbrook.mi.engine` into stage-aware helpers while keeping the current public recompute methods:

- `_recompute_production(production)`
- `_recompute_package(package)`

Add helpers:

- `_stage_values(stage, sequence, is_gate=True, workcenter=False)`
- `_create_stage_check(values, stage, sequence, is_gate=True, workcenter=False)`
- `_stage_rollup_from_checks(checks)`
- `_saw_checks_from_panels(panels, summary)`
- `_cnc_checks_from_panels(panels)`
- `_edgeband_checks_from_panels(panels, summary)`
- `_assembly_stage_checks_from_panels(panels)`
- `_delivery_checks_from_dimensions(width_mm, height_mm, depth_mm)`
- `_install_checks_from_dimensions(width_mm, height_mm, depth_mm)` remains and becomes stage-aware.

Keep existing behavior compatible by making old helper names call the new stage helpers where useful.

## Error Handling

- Malformed edge-banding JSON should not crash recompute. It should create a warning and continue with safe fallback behavior.
- Missing optional data should create a check only when the production stage depends on that data.
- Recompute should continue creating all possible checks so a manager sees the full problem set, not only the first failure.

## Testing

Use focused Odoo TransactionCase tests for:

- Stage field values on generated checks.
- Stage rollup chooses the first blocked stage by production sequence.
- Existing cut, hardware, assembly, handling, and install checks still fire.
- New edgeband malformed JSON warning.
- New stage blocker counts on packages.
- Manager views load.

Use live rollback-only Odoo shell verification on QNAP for deployment because full test runs have previously hit memory limits.

## Deployment Notes

- Update the addon version from `19.0.1.0.0` to `19.0.1.1.0`.
- Deploy only `southbrook_manufacturing_intelligence` files.
- Run a no-test module update first.
- Verify `/web/health` and container health after update.
- Run focused shell assertions for stage fields, rollups, and representative checks.

## Out of Scope

- Custom JavaScript dashboard widgets.
- MES-style machine telemetry integration.
- Real CNC post validation.
- Automated nesting optimization.
- Barcode scanning workflows.

These can be added later after the stage-gate model is stable.
