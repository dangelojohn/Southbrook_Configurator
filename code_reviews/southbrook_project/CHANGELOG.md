# Changelog — `southbrook_project`

## 19.0.0.2.0 — 2026-07-10 (code review #3)

A low-defect module: one perf fix, a testability refactor, doc corrections,
and a first test suite. No behavior change to shipped views/fields.

### Fixed
- **Perf (N+1):** `_compute_southbrook_top_level_task_count` now uses a single
  batched `_read_group` aggregate instead of a per-record `search_count()`
  loop, and gained `@api.depends("task_ids.state", "task_ids.parent_id",
  "task_ids.project_id")` so it refreshes correctly (previously it could go
  stale — no dependency graph).
- **Docs:** removed the manifest's unimplemented "email alias on project 1"
  claim; README now describes the real `post_init` hook (not the non-existent
  `data/project_1_defaults.xml`) and the corrected plural
  `.o_kanban_project_tasks` SCSS selector.

### Changed
- Extracted the backfill logic into `project.project._southbrook_backfill_defaults()`
  (hook delegates to it) so it is unit-testable; corrected the idempotency
  comment (Boolean flags can't distinguish "unset" from "operator set False").
- Removed an unused `_` import.

### Added
- `tests/` (was zero coverage): 7 tests — top-level task count (subtask/closed
  exclusion + recompute-on-close), display_name SO suffix, priority default,
  backfill fill-blanks idempotency + operator-value preservation.

### Known / owner decision (unchanged)
- `views/project_views.xml`'s top-level-count kanban view still ships
  `active="False"` — the module's headline fix is dormant. The N+1 is fixed so
  it is now safe to activate; flipping it is a UX decision left to the owner.

### Verified clean (no change)
All v19 axes, the `_compute_display_name` override, the `post_init_hook(env)`
signature, real (non-Studio) `x_` fields, and the whole security surface. See
`REVIEW_REPORT.md`.
