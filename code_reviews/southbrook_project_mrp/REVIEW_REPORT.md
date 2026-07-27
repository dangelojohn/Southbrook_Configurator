# Code Review — `southbrook_project_mrp`

**Module #29 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.3.0 → **19.0.1.4.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+perf; v19+correctness) → independent
source verification → HEAD baseline → minimal real fixes + test repairs → live `-i`
+ `-u` + tests on isolated DB (`ci_projmrp`, full southbrook dep stack staged).

---

## What the module does

Coordination layer mapping customer jobs (`project.task`) ↔ manufacturing (MRP):
readiness engine, MO/WO linkage, a kanban pipeline, a bottleneck-contention view, a
production-release checklist, and a non-destructive data-quality report.
`project_task.py` is 2411 lines and carries the bulk of the readiness computes.

---

## Verdict

**No security vulnerabilities** (state coordination is sound, `@api.depends` is
registry-safe, no injection). The module was, however, **substantially pre-broken
on the current v19c build** (20 errors + 1 fail of its own 58 tests) from a
**missed v19 field-removal** and a **runtime-breaking non-stored field in a menu
action** — both fixed. The audit also surfaced real **performance** issues (query
storms on filter clicks); the clearest self-contained one is fixed, the rest
documented.

---

## Findings

### Fixed — v19 correctness (were breaking the module)

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| C1 | HIGH (runtime) | **`project_task.py` read the v19-removed `mrp.workcenter.equipment_ids`** (`_compute_equipment_readiness`). The v19 port fixed the sibling spot in `mrp_workorder._southbrook_start_blocker` but **missed this one** → `AttributeError` on every access (16+ tests errored; the field feeds `equipment_blocked`, which cascades through the whole readiness chain). | Walk the forward path `maintenance.request.equipment_id.workcenter_id` (guarded on `equipment_id` presence), mirroring the sibling. |
| C2 | HIGH (web-client) | **The "Bottleneck Contention" menu threw the moment it was opened.** `current_bottleneck_workcenter_id` is a **non-stored** computed field, yet the action both filters `[('current_bottleneck_workcenter_id','!=',False)]` and default-`group_by`s on it — searching/`read_group` on a non-stored field with no `_search` raises. The same action's domain also used the non-searchable computed `production_count`. | `store=True` on `current_bottleneck_workcenter_id` (its `@api.depends` already covers the derivation, so storing is deterministic); action domain `production_count > 0` → searchable `production_ids != False`. |

### Fixed — performance

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| P1 | HIGH (perf) | **Three *stored* readiness-state fields carried a `search=` method that did `search([]).filtered()`** — a full-table scan that discards the indexed column. Verified in v19 core (`domains.py:955-961`): the ORM calls a field's `search=` **even when stored**, so the most-used filters (`manufacturing_blocked`/`review`/`ready`) and every `project_project` action filtering on these ran a full scan instead of a `WHERE`. | **Removed the `search=`** on `manufacturing_readiness_state`, `southbrook_production_release_state`, `southbrook_install_readiness_state` — the stored column is directly searchable (identical results, all operators, indexed). |

### Documented (perf refactor / business-policy — not unilaterally changed)

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| P2 | HIGH (perf) | The **non-stored boolean** readiness fields (`material_at_risk`, `crew_gap`, `equipment_blocked`, `workcenter_over_capacity`, `job_at_risk`, …) back search-view filters via generic `_search_*_compute` helpers that do `search([]).filtered()`, **forcing the whole readiness engine (per-task `PurchaseLine`/`StockMove`/`maintenance.request` searches) over every task in the DB on a single filter click.** | Store+index the derived booleans (they have full `@api.depends`), or push a real SQL domain. NOT done here: naive scan-scoping (`production_ids != False`) changes the semantics of negative queries (`=False` should still return non-manufacturing tasks) — needs the store-the-booleans approach, a correctness-sensitive change across ~10 fields. |
| P3 | MEDIUM (perf) | `_compute_southbrook_mission_control` + the ~15 `action_southbrook_open_*` load all project tasks and run the non-stored readiness computes; opening any project form triggers it (count fields drive `invisible=` on buttons). | Scope domains to `[('production_ids','!=',False)]`; prefer `read_group`/stored flags. |
| P4 | MEDIUM (perf+scope) | `action_southbrook_data_quality_dry_run` does **global** (not project-scoped) orphan-MO search + full-table `stock.scrap`/`mrp.unbuild` scans, surfacing other projects'/companies' records to any `group_user`. | Scope through the project's tasks/MOs; replace `search([]).filtered(display_name)` with a domain. |
| P5/P6 | LOW (perf) | Kanban recomputes non-stored `job_at_risk`/`components_available`/`eco_pending_count` per render; `_compute_readiness_line_count` builds ~13 dicts to return a constant. | Store the two kanban flags; short-circuit the line count. |
| S1/S2 | LOW (sudo) | `action_recompute_readiness_lines` sudo-writes readiness lines without a task-level write check; maintenance reads use `.sudo()` (cross-company inference). | Business-policy; add a task write-check / drop `.sudo()` if ACLs permit. |
| — | — | **Cross-module test artifacts**: `test_project_task_exposes_manufacturing_calculations` needs `southbrook_manufacturing_intelligence` (not a dep) → now `skipTest` when absent; `test_mo_create_backlinks` hit `southbrook_mrp_pm`'s approval gate → test now force-releases. | — |

---

## Strong positives (verified)

- **No `@api.depends` registry-break trap** anywhere — the discipline of
  "`getattr` in the body, never in `@api.depends`" is applied consistently; all
  cross-module fields named in depends resolve to their defining dep.
- **State coordination is sound** — MO↔task linking is idempotent; the readiness
  stage-gate reads the *stored* `manufacturing_readiness_state`, honors a context
  skip flag, and blocks terminal moves; no unguarded coordination-state writes.
- **No injection / unsafe render**; optional models guarded with `"model" in
  self.env`; `stock.scrap`/`mrp.unbuild` linkage guarded with `"field" in _fields`;
  Datetime-vs-Date `.date()` guards present.
- **v19-clean install**: no `<function obj()>` trap, `models.Constraint`,
  `@api.model_create_multi`, all inherited view xmlids exist.

---

## Validation

- `-i southbrook_project_mrp` (fresh DB) — **clean install**, registry ~39 s.
- `-u southbrook_project_mrp` — **clean upgrade** (incl. the `store=True` column).
- Tests `--test-tags=/southbrook_project_mrp` — **58/58 pass, 0 failed, 0 errors**
  (1 skipped: MI-dependent), from a baseline of **20 errors + 1 fail**. See
  `TEST_RESULTS.md`.
