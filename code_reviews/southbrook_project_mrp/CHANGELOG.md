# Changelog — `southbrook_project_mrp`

## 19.0.1.4.0 — 2026-07-11 (code-review pass, module #29)

### v19 correctness — Fixed (were breaking the module)
- **C1** — `_compute_equipment_readiness` (`project_task.py`) read the v19-removed
  `mrp.workcenter.equipment_ids`, raising `AttributeError` on every access (the port
  fixed the sibling `mrp_workorder` spot but missed this one). Now walks the forward
  path `maintenance.request.equipment_id.workcenter_id`, guarded on `equipment_id`
  presence — mirrors `mrp_workorder._southbrook_start_blocker`.
- **C2** — `current_bottleneck_workcenter_id` is now **`store=True`**: the
  "Bottleneck Contention" action filters and group_by's on it, and a non-stored
  computed field raises at search/`read_group` time (the menu threw on open). Its
  `@api.depends` already covers the derivation, so storing is deterministic. The
  action domain's non-searchable `production_count > 0` → searchable
  `production_ids != False`.

### Performance — Fixed
- **P1** — removed the redundant `search=` method on the three **stored**
  readiness-state fields (`manufacturing_readiness_state`,
  `southbrook_production_release_state`, `southbrook_install_readiness_state`). v19
  calls a field's `search=` even when stored, so these forced a full-table
  `search([]).filtered()` on the module's most-used filters instead of using the
  indexed column. Removed → indexed searches, identical results.

### Tests
- Repaired pre-existing failures unmasked/caused on the current build:
  `test_w029_bottleneck_contention_search_view_exposes_group_by` (assert against the
  inheriting view `project_task_search_bottleneck_group` that defines the filter),
  `test_w029_..._action_is_grouped_by_workcenter` (`production_ids` not
  `production_count`), `test_mo_create_backlinks_to_job` (force-release past the
  mrp_pm approval gate), `test_phase1_..._plain_language` (accept the legit "Confirm
  cabinet specs" next-action), `test_project_task_exposes_manufacturing_calculations`
  (`skipTest` when `southbrook.mi.check` / MI is absent).

### Not changed (documented in REVIEW_REPORT.md)
- P2 (store the non-stored boolean readiness fields to fix the filter-click query
  storm — correctness-sensitive across ~10 fields), P3 mission-control compute, P4
  data-quality dry-run scoping, P5/P6 kanban/line-count, S1/S2 sudo business-policy.
