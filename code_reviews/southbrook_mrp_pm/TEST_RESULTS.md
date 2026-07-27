# Test Results — `southbrook_mrp_pm`

**Date:** 2026-07-11
**DB:** isolated on `v19c-db` (created via db-local socket to sidestep an OrbStack
ephemeral-port storm — see `southbrook_room_capture` REVIEW_REPORT env note).
**Addons:** full southbrook dep stack staged into `/mnt/extra-addons`.

## Baseline (unmodified HEAD, current v19c build)
`-i` with broad tags: **13 failed, 4 error(s) of 449 tests**.
Scoped to the module's own suite (`--test-tags=/southbrook_mrp_pm`):
**5 failed + 2 error(s) of 29** — i.e. **7 own-module failures** pre-existing on
this (newer-than-prod) build. Install itself was clean (no data-file blocker).

## After fixes
```
odoo -c … -i southbrook_mrp_pm --test-enable --test-tags=/southbrook_mrp_pm --stop-after-init --no-http
```
- Fresh cold install — 118 modules, registry 34.1 s, no ERROR/CRITICAL.
- `0 failed, 0 error(s) of 32 tests` (1 skipped — MI-dependent).

```
odoo -c … -u southbrook_mrp_pm --test-enable --test-tags=/southbrook_mrp_pm …
```
- Clean upgrade — `0 failed, 0 error(s) of 32 tests`. Idempotent.

## Baseline failures — all resolved
| Test | Baseline | Resolution |
|------|----------|------------|
| `test_so_blocked_without_approval` | FAIL | rewritten to the MO-create-gate design |
| `test_so_bypass_with_manager_flag` | FAIL | rewritten + new bypass audit asserted |
| `test_30_view_inflight_workorders_action_shape` | ERROR | test bug (set→list) |
| `test_40_view_impacted_productions_action_shape` | ERROR | test bug (set→list) |
| `test_route_registered` (w056) | FAIL | v19 attr drift (`.original_routing`) |
| `test_old_done_activity_purged` (w057) | FAIL | `flush_recordset()` + test-safe commit |
| `test_at_risk_when_mi_blocked_within_window` (w019) | FAIL | `skipTest` (MI not installed) |

## New regression tests (all green)
| Test | Asserts |
|------|---------|
| `test_state_laundering_blocked_for_non_approver` | non-approver RPC-write to `production_approval_state='approved'` → `AccessError` |
| `test_force_release_self_grant_blocked_for_non_manager` | non-manager RPC-write `force_production_release=True` → `AccessError` |
| `test_approve_action_requires_approver_group` | non-approver `action_approve_production()` → `AccessError` |

## Not addressed here (pre-existing, documented)
- Dependency `southbrook_estimating_website` tests
  `test_send_to_manufacturing.test_rejects_draft_order_with_wrong_state`
  (`'not_approved' != 'wrong_state'`) and `test_re_fire_reuses_existing_mo` — a
  cross-module precedence artifact that surfaces only when mrp_pm's approval gate
  is installed. Belongs to a combined-stack test pass on the dependency module.
