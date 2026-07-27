# Test Results — `southbrook_os_kernel` v19.0.1.1.0

**Date:** 2026-07-10
**Runtime:** Odoo 19.0-20260513 CE (local `v19c-odoo` container), Postgres 16
**Method:** module staged into the container addons path against an **isolated throwaway DB** (`os_kernel_ci`); prod (QNAP) never touched. Environment restored afterward (staging copy + CI DB removed).

## 1. Static validation — PASS
| Check | Result |
|-------|--------|
| `python -m py_compile` (all models + tests) | PASS |
| XML well-formedness (all 11 data/view files incl. new `ir_rule.xml`, `ir_cron.xml`) | PASS |
| `ir.model.access.csv` column integrity | PASS (8 cols, 10 rows) |
| Manifest parses; all 12 data files exist on disk | PASS |
| View field references resolve to model fields | PASS |

## 2. Cold install — PASS
`odoo -d os_kernel_ci -i southbrook_os_kernel --test-enable --stop-after-init` on a **fresh database** (base + mail + 26 dependency modules auto-installed).
```
Module southbrook_os_kernel loaded in 0.17s, 504 queries
```
All data files loaded without error, including the new `security/ir_rule.xml`.

## 3. Upgrade — PASS
`odoo -d os_kernel_ci -u southbrook_os_kernel` on the already-installed DB (simulates the prod upgrade path 19.0.1.0.0 → 19.0.1.1.0). Schema migration (3 new indexes), new cron, and new record rule applied cleanly; suite re-ran green.
```
Module southbrook_os_kernel loaded in 0.15s, 370 queries
```

## 4. Automated tests — PASS (53 tests, 0 failed, 0 errors)
`--test-enable --test-tags southbrook_os_kernel`
```
odoo.tests.stats: southbrook_os_kernel: 53 tests 0.11s 664 queries
odoo.tests.result: 0 failed, 0 error(s)
```
Coverage includes the 8 tests added by this review:
- `test_constraints.py` — duplicate-`create()` rejection for all 4 `models.Constraint`
  (switch.key, memory namespace+key, agent.code, tool.code) + composite-key positive case.
- `test_ledger.py` — caller provenance (ledger records the real non-superuser caller, not OdooBot),
  retention prune, and retention `<= 0` opt-out.

### Note — one iteration during the run
The provenance test initially failed (`AssertionError: 1 == 1`): Odoo's `TransactionCase`
runs as SUPERUSER, so the default env couldn't distinguish caller from superuser. The
**fix under test was correct**; the test was corrected to drive `run()` as a freshly-created
non-superuser internal user (`with_user`), after which it passes and genuinely proves the
provenance fix. No production code changed as a result.

## 5. Database object verification — PASS
Queried `pg_indexes` / `ir_cron` on the installed DB:
```
idx:southbrook_os_ai_request__create_date_index   ✓
idx:southbrook_os_ai_request__user_id_index       ✓
idx:southbrook_os_memory__expires_at_index        ✓
cron:OS Kernel: prune AI request ledger           ✓
```
The multi-company `ir.rule` (`rule_os_ai_request_company`) loaded during install without error.

> During verification, DB evidence caught that the `os_memory.expires_at` index (R2c) had
> not actually been applied in the first pass — it was then applied and re-verified. This is
> exactly why the review validates against a live DB rather than trusting the diff.

## Overall: PASS
Cold install ✓ · Upgrade ✓ · 53 tests green ✓ · all schema objects present ✓ · no regressions.
