# Southbrook Premium MRP Orchestration

Closes the data-flow loop the underlying southbrook_* modules already
have schemas for: always-on `project.task` spine, MO backlink, MI
recompute crons, tool-asset telemetry, generative + planning
activation. Phase 1.1 onward.

## Audit P-tasks owned here

### P1 — Auto-emit cutlist on confirm

`sale.order.action_confirm` calls `_southbrook_emit_cutlists()` after
the existing spine + MO-backlink path. The method delegates to
`sb.production.package.build_from_order_line` per order line. Gated
behind `ir.config_parameter
southbrook_premium_orchestration.auto_emit_cutlist` (default **OFF**).
Flag-OFF is byte-identical to the pre-P1 baseline.

### P7 — Specs single source of truth (sync side)

`_create_kitchen_project_task` now calls
`task._southbrook_p7_sync_from_so()` after task creation (both
new-task and existing-task re-confirm paths). The sync itself lives in
`southbrook_project`. Wrapped in `try/except` so a sync failure never
blocks spine creation.

## Tests

```
test_phase1_spine
test_phase2_practical_loop
test_phase3_generative
test_full_flow
test_p1_auto_emit_cutlist       (P1)
test_golden_path_all_flags_on   (P1+P2+P3+P5 DoD)
```

## Rollback

P1 → flip `auto_emit_cutlist=False`. P7 → tick
`project.task.x_southbrook_specs_override=True` per record. Both are
`git revert`-safe.

## Feature flags

See `docs/FEATURE_FLAGS.md` for the canonical index of all P1–P8 flags.
