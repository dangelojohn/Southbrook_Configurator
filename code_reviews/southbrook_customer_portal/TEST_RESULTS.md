# Test Results — `southbrook_customer_portal`

**Date:** 2026-07-11 · **DB:** isolated on `v19c-db` · full southbrook stack staged.

## Baseline (unmodified HEAD)
`-i --test-tags=/southbrook_customer_portal`: **0 failed, 0 error(s) of 9 tests** —
the module installs and tests clean on the current v19c build.

## After fixes
- `-i` (fresh DB) — registry 41.7 s, no ERROR/CRITICAL — **0 failed, 0 error(s) of
  10 tests**.
- `-u` — **0 failed, 0 error(s) of 10 tests**.

## New regression test
| Test | Fix |
|------|-----|
| `test_select_option_blocked_after_approval` | F1 — select route refuses to change the design option once the project is approved (real CSRF token from `/my/fabio`, so the state gate is what blocks) |

**Total: 10/10 pass on `-i` and `-u`. No regressions** (F1 state gate + F3
date_decided don't affect the existing editable-state flows).
