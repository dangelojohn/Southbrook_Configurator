# Test Results — `southbrook_mrp_kitchen_tools`

**Date:** 2026-07-11
**DB:** isolated on `v19c-db` (created via db-local socket — see
`southbrook_room_capture` REVIEW_REPORT env note).
**Addons:** full southbrook dep stack staged into `/mnt/extra-addons`.

## Baseline (unmodified HEAD)
`-i --test-tags=/southbrook_mrp_kitchen_tools`: **0 failed, 0 error(s) of 67
tests** — the module (including its 162-record data seed) installs and tests clean
on the current v19c build. (The `button_start` crash V1 is a runtime-UI defect the
tests don't exercise — they call `button_start()` without the v19 kwarg.)

> Note: the first `-i` attempt exited 137 (transient OrbStack VM OOM/SIGKILL under
> load); a retry ran clean. Not a module issue.

## After fixes
```
odoo -c … -i southbrook_mrp_kitchen_tools --test-enable --test-tags=/southbrook_mrp_kitchen_tools --stop-after-init --no-http
```
- Fresh cold install (incl. the 162-record seed) — registry 39.5 s, no
  ERROR/CRITICAL.
- `0 failed, 0 error(s) of 74 tests`.

```
odoo -c … -u southbrook_mrp_kitchen_tools --test-enable …
```
- Clean upgrade — `0 failed, 0 error(s) of 74 tests`.

## New regression tests (7, all green)
| Test | Fix |
|------|-----|
| `test_qr_checkout_marks_asset_checked_out_and_attributes_operator` | H1/H2 |
| `test_qr_double_checkout_is_rejected` | H1 |
| `test_qr_checkin_returns_asset_to_available` | H1 |
| `test_negative_quantity_rejected` | H3 |
| `test_negative_unit_cost_rejected` | H3 |
| `test_button_start_accepts_v19_raise_on_invalid_state_kwarg` | V1 |
| `test_readiness_counts_grandchild_category_asset` | M2 |

**Total: 74/74 pass on both `-i` and `-u`. No regressions** (all 67 pre-existing
tests remained green — the checkout/attribution changes, non-negative constraints,
and `child_of` match produce identical results for the existing fixtures).
