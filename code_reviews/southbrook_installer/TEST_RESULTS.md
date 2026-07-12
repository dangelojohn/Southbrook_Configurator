# Test Results — `southbrook_installer` v19.0.4.0.0

**Date:** 2026-07-10
**Runtime:** Odoo 19.0-20260513 CE (local `v19c-odoo` container), Postgres 16
**Method:** module staged into the container addons path against an isolated
throwaway DB (`inst_ci2`); prod untouched; environment restored afterward.

## 0. Baseline (as-shipped) — GREEN
```
southbrook_installer: 0 failed, 0 error(s) of 25 tests
```
The module shipped with a passing suite and clean cold install (0 deprecation
warnings) — a healthy starting point. The two critical defects (dead v19 bus
API, missing record rules) were *latent* — swallowed / undocumented — so the
green baseline did not reveal them; the audit did.

## 1. Static validation — PASS
`python -m py_compile` (all models + tests); XML well-formedness incl. the new
`security/southbrook_installer_record_rules.xml` — PASS.

## 2. Cold install — PASS
`odoo -d inst_ci2 -i southbrook_installer --test-enable` on a fresh DB —
`Module southbrook_installer loaded ... 1375 queries`, all data/security/views/
reports loaded (14 record rules applied).

> During validation this caught a real error: an initial attempt to add
> `groups_id` to the dispatch-board `ir.actions.client` failed install
> (`Invalid field 'groups_id' in 'ir.actions.client'` — v19 has no such field).
> Reverted; gating is by menu + record rules instead. This is exactly why the
> review validates against a live install.

## 3. Automated tests — PASS (28 tests, 0 failed, 0 errors)
```
odoo.tests.result: 0 failed, 0 error(s) of 28 tests
```
25 pre-existing + 3 added by this review:
- `test_dispatcher_bus_notify_does_not_raise` — proves the `_sendone` fix
  (previously raised `AttributeError` on `_sendmany`).
- `test_crew_sees_only_assigned_jobs` — a helper sees jobs they lead or crew,
  **not** unassigned jobs (record-rule scoping works).
- `test_dispatcher_sees_all_jobs` — a dispatcher retains company-wide
  visibility (no lockout of broad roles).

## 4. Database object verification — PASS
```
idx:southbrook_installer_job__stage_is_terminal_index                 ✓
stored_cols: tool_loan_count,tool_loan_open_count,stage_log_count,stage_log_done_count  ✓
installer_record_rules: 14                                            ✓
```

## Overall: PASS
Cold install clean ✓ · 28/28 tests green (from 25, +3 for the two criticals) ✓ ·
CRITICAL bus fix + record-rule security model verified ✓ · schema objects present ✓.
