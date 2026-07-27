# Test Results — `southbrook_dealer_portal`

**Date:** 2026-07-11 · **DB:** isolated on `v19c-db` · full southbrook stack staged.

## Baseline (unmodified HEAD)
`-i --test-tags=/southbrook_dealer_portal`: **0 failed, 0 error(s) of 11 tests** —
green, but the suite only covered the CHANNEL gate; the two id-bearing export
routes had **no object-auth test**, which is why the CRITICAL IDORs (C1/C2) were
not surfaced by tests.

## After fixes
- `-i` (fresh DB) — registry 43.2 s — **0 failed, 0 error(s) of 13 tests**.
- `-u` — **0 failed, 0 error(s) of 13 tests**.

## New regression tests (2, green)
| Test | Fix |
|------|-----|
| `test_dealer_cannot_export_another_partners_package` | C1/C2 — a dealer gets not-found (no `southbrook.kd_flatpack` in the body) for a package owned by a different partner's order |
| `test_dealer_can_export_own_package` | positive — the owning dealer still gets 200 + the KD envelope |

**Total: 13/13 pass on `-i` and `-u`. No regressions** (the record-rule scoping +
controller ownership check don't affect the existing channel-gate or model-level
export tests).
