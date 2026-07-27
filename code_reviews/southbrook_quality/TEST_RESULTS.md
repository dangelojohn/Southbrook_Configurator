# TEST_RESULTS — southbrook_quality

**DB:** `ci_qual38` (isolated, full southbrook MI + kitchen_mrp dep stack at `/mnt/extra-addons`)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Baseline (HEAD, before fixes)
`-i` + `--test-tags=/southbrook_quality`: install clean (~63 s), **2 failed of 14**.
- `test_cpk_view.test_cpk_computed_for_capable_process` **FAIL** — the SQL-view Cpk
  report returned no row (ORM sample INSERTs not flushed before the raw view SELECT).
- `test_ncr_workflow.test_time_to_close_hours_computed` **FAIL** —
  `-0.00024… not greater than 3.0` (back-dated `create_date` write silently ignored by
  v19; `create_date`/`closed_at` clock skew yielded a small negative).

## After fixes (19.0.2.0.0)
```
southbrook_quality: 16 tests
0 failed, 0 error(s) of 16 tests when loading database 'ci_qual38'
```

| Phase | Result |
|-------|--------|
| `-i southbrook_quality` (fresh DB, incl. new `opened_at` column + SQL Cpk view + mi_tiles seed) | **clean**, registry ~63 s |
| `-u southbrook_quality` | **clean**, 2.0 s |
| `--test-tags=/southbrook_quality` (16 tests) | **16 pass / 0 fail / 0 error** |

## New / repaired tests
- `test_raw_write_state_is_guarded` — `write({"state":"released"})` on a draft raises
  and leaves state `draft` (N1).
- `test_critical_release_requires_manager` — a non-manager cannot `action_release` a
  critical NCR (N2).
- `test_time_to_close_hours_computed` — now back-dates `opened_at`; asserts >3 h.
- `test_cpk_computed_for_capable_process` — flushes before the view query; Cpk row
  present, `cpk > 0`, `sample_count == 30` (still holds under the S1 `STDDEV_SAMP` fix).

## Probe evidence
- `write({"create_date": now-4h})` then re-read → `create_date` **unchanged** (v19
  ignores writes to the magic field) — the root cause of the time-to-close bug; hence
  the explicit writable `opened_at`.

## Notes
- The `@class`/RST warnings + one `sms` "Unavailable during module installation" line
  during `-i` originate from other modules / core demo data — pre-existing, unrelated,
  non-fatal (registry loads, all tests pass).
