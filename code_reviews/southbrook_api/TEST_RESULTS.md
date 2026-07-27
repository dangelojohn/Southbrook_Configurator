# Test Results — `southbrook_api`

**Date:** 2026-07-11
**DB:** isolated on `v19c-db` (created via db-local socket — see
`southbrook_room_capture` REVIEW_REPORT env note).
**Addons:** full southbrook dep stack staged into `/mnt/extra-addons`.

## Baseline (before fixes)
`-i` on the current staged tree: **1 failed of 35** —
`test_cutlist_nesting.test_envelope_returns_nesting_schema_and_panels`
(`'southbrook.nesting.v2' != 'southbrook.nesting.v1'`): a pre-existing
cross-module schema-version drift (the envelope in `southbrook_kitchen_mrp`
advanced to v2; this module's test constant was stale at v1). Install itself was
clean.

## After fixes
```
odoo -c … -i southbrook_api --test-enable --test-tags=/southbrook_api --stop-after-init --no-http
```
- Fresh cold install — registry 30.9 s, no ERROR/CRITICAL.
- `0 failed, 0 error(s) of 35 tests`.

```
odoo -c … -u southbrook_api --test-enable --test-tags=/southbrook_api …
```
- Clean upgrade — `0 failed, 0 error(s) of 35 tests`. New `ir.cron` + `ir.rule`
  installed; `group_user` ACL on `southbrook.api.key` confirmed `1,0,0,0` in DB.

## New regression tests (F1, both green)
| Test | Asserts |
|------|---------|
| `test_regular_user_cannot_forge_api_key` | a `base.group_user` employee cannot `create` a `southbrook.api.key` row (blocks admin-impersonation forgery) → `AccessError` |
| `test_user_cannot_revoke_another_users_key` | `action_revoke` (+ own-keys record rule) blocks revoking another user's key → `AccessError`, key stays active |

## Modified tests
- `test_health_no_auth_returns_ok_with_schema` — now asserts `db` is **absent** (F9).
- `test_cutlist_nesting` — `NESTING_SCHEMA` `v1` → `v2` (envelope emits v2).

## Pre-existing suite (unchanged, all green)
`test_auth` (login/key/error-envelope), `test_endpoints`, `test_idempotency`,
`test_cutlist_nesting`, `test_flutter_contract`, `test_scenario_sales_manager_setup`.

**Total: 35/35 pass on both `-i` and `-u`. No regressions.**
