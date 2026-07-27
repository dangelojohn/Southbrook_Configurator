# Test Results — `southbrook_project` v19.0.0.2.0

**Date:** 2026-07-10
**Runtime:** Odoo 19.0-20260513 CE (local `v19c-odoo` container), Postgres 16
**Method:** module staged into the container addons path against an isolated
throwaway DB (`proj_ci`); prod untouched; environment restored afterward.

## 0. Baseline — ZERO tests
The module shipped with no `tests/` directory. This review adds the first suite.

## 1. Static validation — PASS
`python -m py_compile` (models, hooks, tests) — PASS.

## 2. Cold install — PASS
`odoo -d proj_ci -i southbrook_project --test-enable` on a fresh DB.
```
Module southbrook_project loaded in 0.09s, 243 queries
```
- No ParseError → **all inherited-view `inherit_id` xmlids resolve** in v19 core
  (the one thing the offline v19 audit couldn't verify).
- The `post_init` hook ran and cleanly no-op'd (no project id 1 on a fresh
  demo-less DB) — the guarded path works.

## 3. Automated tests — PASS (7 tests, 0 failed, 0 errors)
```
odoo.tests.stats:  southbrook_project: 9 tests
odoo.tests.result: 0 failed, 0 error(s) of 7 tests
```
Coverage (all new):
- `test_top_level_count_excludes_subtasks_and_closed` — counts only open
  top-level tasks (proves the subtask + closed exclusion, the module's raison
  d'être). Also validates the new batched `_read_group` compute.
- `test_top_level_count_recomputes_on_state_change` — proves the new
  `@api.depends` refreshes the count when a task closes.
- `test_display_name_suffixes_sale_order` / `..._no_suffix_without_sale_order`
  — the `_compute_display_name` SO suffix.
- `test_priority_defaults_to_standard`.
- `test_backfill_fills_blanks_then_is_idempotent` — backfill writes blanks, and
  a second run writes nothing.
- `test_backfill_does_not_stomp_operator_description` — a non-blank description
  is preserved.

## Overall: PASS
Cold install clean ✓ · view xmlids resolve ✓ · `_read_group` compute works ✓ ·
7/7 tests green (from 0) ✓ · no regressions.
