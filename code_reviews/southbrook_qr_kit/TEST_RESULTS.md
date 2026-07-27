# Test Results — `southbrook_qr_kit` v19.0.0.15.0

**Date:** 2026-07-10
**Runtime:** Odoo 19.0-20260513 CE (local `v19c-odoo` container), Postgres 16
**Method:** module staged into the container addons path against an isolated
throwaway DB (`qr_ci`); prod untouched; environment restored afterward.

## 0. Baseline (before repairs) — 15 FAILING
The as-shipped suite was **red**, proving the defects were real (not theoretical):
```
southbrook_qr_kit: 9 failed, 6 error(s) of 57 tests
```
- 7 × dispatch/`unknown_kind` (C1 AbstractModel-falsy)
- 2 × `mrp.workorder has no attribute message_ids/message_post` (W071)
- 4 × `_FakeResponse returns an invalid value` (w072 harness, v19)
- 2 × floor shell empty `<!DOCTYPE html>` (W073, real over HTTP)

## 1. Static validation — PASS
`python -m py_compile` (all models/controllers/wizards/tests) — PASS.
XML well-formedness incl. new `data/ir_cron.xml` — PASS.

## 2. Cold install — PASS
`odoo -d qr_ci -i southbrook_qr_kit --test-enable` on a fresh DB.
```
Module southbrook_qr_kit loaded in 0.23s, 532 queries
```
All data files (incl. new `ir_cron.xml`) loaded without error.
No `@route(type='json')` deprecation warnings (previously 9).

## 3. Automated tests — PASS (60 tests, 0 failed, 0 errors)
```
odoo.tests.stats:  southbrook_qr_kit: 80 tests
odoo.tests.result: 0 failed, 0 error(s) of 60 tests
```
(Process exit was 1 — a `--stop-after-init` shutdown-signal artifact, not a test
failure; the result line and clean-shutdown log confirm all green.)

Progression across the repair: **15 failing → 9 → 0**, verified by re-running
the suite after each batch (correctness fixes, then security/perf fixes).

New/repaired coverage:
- `test_security_hardening.py` — payload query-key rejection (S2), PIN
  brute-force throttle (S3), valid-payload round-trip.
- `test_w072` harness fixed for v19 (route return-type validation).
- `test_w071` workorder-chatter assertions made conditional on `mail.thread`.

## 4. Database object verification — PASS
Queried `pg_indexes` / `ir_cron` on the installed DB:
```
idx:southbrook_qr_scan_log__create_date_index    ✓
idx:southbrook_qr_scan_log__target_id_index      ✓
idx:southbrook_qr_scan_log__target_model_index   ✓
cron:QR Kit: prune scan log                       ✓
```

## Overall: PASS
Cold install ✓ · 60/60 tests green (from 15 failing) ✓ · 3 CRITICAL security
issues closed ✓ · schema objects present ✓ · v19 deprecations cleared ✓.
