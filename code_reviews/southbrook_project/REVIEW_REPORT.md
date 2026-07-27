# Code Review & Repair Report — `southbrook_project`

**Module:** Southbrook Project · **Version:** 19.0.0.1.0 → **19.0.0.2.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 Community Edition
**Queue position:** #3 of 46 (Tier 0 — leaf; deps `project`, `sale`, both standard)
**Review method:** 3 parallel read-only audit agents + independent source verification + live cold-install/test on Odoo 19 CE.

---

## Executive Summary

Cabinetry-shop polish on stock Odoo Project: 4 custom `x_southbrook_*` fields on `project.task`, a subtask-aware top-level task count on `project.project`, a `post_init` backfill hook, 6 seeded tags, and a responsive-kanban asset.

**This is a well-written, genuinely low-defect module** — clean on every v19-breakage axis: correct `post_init_hook(env)` signature, real ORM fields (not Studio manual `x_` fields, so no view-validation trap despite the `x_` prefix), stored+indexed fields used correctly in domains/group-by, a correct `_compute_display_name` override, `noupdate` seed data, and no ACL/sudo/eval/SQL surface at all (the module's own "no ACL/credential/user-creation" self-claim holds up in code).

The findings were a performance N+1, one functional gap (a headline feature shipped disabled), stale docs, and — the biggest gap — **zero test coverage**. All repaired except the one item that is a genuine owner decision (see Remaining Risks).

---

## Original Issues Found

| # | Sev | Axis | Finding |
|---|-----|------|---------|
| F1 | **HIGH (functional)** | v19/UX | The module's headline fix — replacing the inflated `open_task_count` with `southbrook_top_level_task_count` on the project-overview kanban — ships in a view with `active="False"` (`views/project_views.xml`). The compute exists and is correct but is **never surfaced in the UI**; the kanban still shows the inflated count. Reads as a leftover `active=False` from testing. |
| P1 | MED | Perf | `_compute_southbrook_top_level_task_count` did a `search_count()` **per record in a loop** (N+1, fires once per project card if F1's view is enabled) with **no `@api.depends`** (never joins the recompute graph → can go stale). |
| D1 | LOW | Docs | Manifest claims an "email alias on project ID 1" that is **never implemented**; README references a `data/project_1_defaults.xml` that **does not exist** (the real mechanism is the `post_init` hook) and documents a stale/wrong CSS selector. |
| C1 | LOW | Code | Unused `_` import in `models/project_task.py`. |
| C2 | LOW | Correctness | The hook comment claimed it "won't re-enable flags the operator turned off," but for a Boolean defaulting to `False`, "unset" and "operator-set-False" are indistinguishable — so `if not flag:` always re-enables. Comment overstated the guarantee. |
| — | — | — | **No `tests/` directory — zero coverage.** |

### Reviewed and found clean (no action)
v19 axes (constraints, groups, cron, AbstractModel, decorators, `env.company`, `<list>`/`attrs`), the `_compute_display_name` override (`@api.depends` correct, calls `super()`), the `post_init_hook(env)` signature, all four `x_southbrook_*` fields (real stored fields, correctly indexed where filtered), the seed data (`noupdate`), and the entire security surface (no new model → no ACL needed; no sudo/eval/SQL; JS bundle clean).

---

## Repairs Completed
1. **P1:** `_compute_southbrook_top_level_task_count` rewritten to a single batched `_read_group` aggregate + `@api.depends("task_ids.state", "task_ids.parent_id", "task_ids.project_id")` — one query for the whole recordset, and the count now refreshes when a task closes/moves.
2. **C2 + testability:** extracted the backfill blank-fill logic into `project.project._southbrook_backfill_defaults()` (returns the list of filled fields); the hook now delegates to it. Corrected the idempotency comment to be honest about the Boolean-flag limitation.
3. **D1:** manifest email-alias claim removed; README updated to describe the actual `hooks.py` mechanism (not the non-existent XML file) and the corrected plural `.o_kanban_project_tasks` selector.
4. **C1:** removed the unused `_` import.
5. **Tests:** new `tests/` with 7 tests — top-level count (subtask + closed exclusion, and recompute-on-close), display_name SO suffix (with/without), priority default, and backfill (fill-blanks idempotency + operator-value preservation).

### Deliberately NOT changed
- **F1 (the `active="False"` view):** flipping it changes the project-overview kanban for every user — a UX/behavior decision that is the owner's to make (it may have been disabled deliberately). The N+1 is now fixed, so it is **safe to activate**; see Remaining Risks. Left as a one-line change for owner sign-off rather than flipped unilaterally.
- **Global `KanbanArchParser` patch** (`kanban_template_field_ids.esm.js`): applies to all backend kanbans (auto-adds `many2many_tags` to widget-less m2m fields). Broad, but it works and scoping it risks breaking the project kanban it exists for. Documented.
- **Hardcoded `browse(1)`** in the hook: fragile but correctly guarded (`.exists()`, blank-only writes). Intentional workaround for a UI-created project with no xmlid.
- **`x_southbrook_sale_order_id` m2o display-name side-channel:** inherent Odoo ORM behavior (m2o `display_name` shown regardless of `sale.order` ACL); not a full-record leak. In a single-tenant shop, project users generally have sales visibility anyway. Documented.

---

## Files Changed
4 modified (`__manifest__.py`, `README.md`, `hooks.py`, `models/project_task.py`), 1 new dir (`tests/`, 2 files). No fields removed, no view behavior changed (the disabled view stays disabled).

## Database Impact
None structural. The child-count field is non-stored (compute-on-read); no new columns/indexes/tables. Fully forward-compatible.

## Security Improvements
None needed — module was already clean. (One informational m2o side-channel documented, not code-changed.)

## Performance Improvements
Child-count compute: per-record `search_count` N+1 → single batched `_read_group` aggregate; now correct under the recompute graph.

## Testing Results
_See `TEST_RESULTS.md`._ Cold install clean on Odoo 19 CE; **7/7 tests pass** (from 0). Install also confirmed every inherited-view xmlid resolves and `_read_group` behaves as written.

## Remaining Risks
1. **F1 — activate the top-level-count kanban view?** As shipped, the module's headline fix is dormant (`active="False"`). The N+1 is now fixed, so activating is safe — but it changes the project-overview kanban for all users. **Owner decision:** flip to `active="True"` to deliver the advertised fix, or keep staged and note it as intentional.
2. Global kanban-parser patch blast radius (LOW) — confirm the app-wide `many2many_tags` auto-widget is intended.
3. Hardcoded `browse(1)` (LOW) — any DB where id 1 is not the intended "Test" project would be silently mutated on install; guarded but portable-only by luck.

## Recommendations
- Decide F1 (activate vs. document-as-staged).
- Consider a `_read_group`-friendly `store=True` on the count only if it later needs to be grouped/filtered.
