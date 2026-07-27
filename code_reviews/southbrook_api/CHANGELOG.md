# Changelog — `southbrook_api`

## 19.0.2.0.0 — 2026-07-11 (code-review pass, module #28)

### Security — Fixed
- **F1 (HIGH) — API-key forgery / privilege escalation.**
  - `security/ir.model.access.csv`: `base.group_user` on `southbrook.api.key`
    reduced from `1,1,1,0` to **read-only `1,0,0,0`** (removes create/write that
    let any employee forge a key row pointing at an admin `user_id`).
  - Added `security/southbrook_api_security.xml` with an `ir.rule`
    `[('user_id','=',user.id)]` scoping backend access to the user's own keys.
  - `southbrook_api_key.action_revoke` now verifies the caller owns the key
    (or is an admin) and writes under sudo (group_user is now read-only).

### Correctness / operational — Fixed
- **F2/F3 (MEDIUM)** — `southbrook_api_idempotency.stash` now wraps its `create`
  in `with self.env.cr.savepoint():` so a concurrent same-`Idempotency-Key`
  unique-violation no longer poisons the cursor (which caused a 500 + rollback of
  the handler's real work).
- **F4 (MEDIUM)** — added `southbrook_api_idempotency._gc_expired()` (batched,
  test-safe commit via `config['test_enable']`) and a daily `ir.cron`
  (`data/ir_cron.xml`, v19 schema) to purge expired records; the promised GC cron
  had never shipped, so the table grew unbounded.
- **F6 (MEDIUM)** — added a global daily cap + kill-switch on the paid AI
  photo-analysis path (`_analyze_quota_ok`,
  `ir.config_parameter southbrook_api.max_daily_analyses`, default 500; 0 =
  kill-switch), checked in `upload_photo` before the analysis.
- **F8 (LOW)** — `_fetch_project_or_404` now guards `not partner or ...` so a
  partnerless user can't read partnerless projects.
- **F9 (LOW)** — `/api/v1/health` no longer returns the DB name.

### Tests
- `test_health_...` updated to assert the `db` field is absent.
- `test_cutlist_nesting` `NESTING_SCHEMA` updated `v1` → `v2` (the envelope emits
  v2; input accepts both) — pre-existing cross-module drift.
- Added `test_regular_user_cannot_forge_api_key` and
  `test_user_cannot_revoke_another_users_key` (F1 regression).

### Not changed (documented in REVIEW_REPORT.md)
- F2/F3 deeper (body-hash + reserve-before-execute to stop double-execution and
  wrong-body replay — needs a schema change + 409/422 decision), F5 login timing
  (Odoo-inherent residual), F6 login brute-force throttle (shared-store limiter),
  F7 credential sprawl (max-active-keys policy).
