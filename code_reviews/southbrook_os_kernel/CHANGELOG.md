# Changelog — `southbrook_os_kernel`

## 19.0.1.1.0 — 2026-07-10 (code review #1)

Operational hardening + test coverage from the professional v19-CE review.
No change to existing model logic, field semantics, or public API. Fully
backward-compatible; upgrade-only (no data migration).

### Added
- **AI request ledger retention.** `southbrook.os.ai.request.autovacuum()`
  prunes rows older than `os.ai.ledger_retention_days` (config param, default
  `90`; `<= 0` = keep forever). Chunked 1000-row deletes. New daily cron
  `ir_cron_os_kernel_prune_ledger`. Closes unbounded ledger growth.
- **Multi-company record rule** on the ledger (`security/ir_rule.xml`,
  `rule_os_ai_request_company`) — scopes rows to the user's allowed companies.
- **Indexes**: `os_ai_request.user_id`, `os_ai_request.create_date`,
  `os_memory.expires_at`.
- **Tests**: `tests/test_constraints.py` (5 — direct duplicate-`create()`
  enforcement of every `models.Constraint`, plus composite-key positive case);
  `tests/test_ledger.py` (3 — caller provenance + retention prune/opt-out).

### Fixed
- **Ledger provenance.** `os.ai.kernel._safe_log` now stamps the real caller's
  `user_id` before the `sudo()` create; previously every ledger row was
  attributed to SUPERUSER/OdooBot, defeating per-user cost attribution.

### Changed
- Manifest version `19.0.1.0.0` → `19.0.1.1.0`; registered
  `security/ir_rule.xml`.

### Reviewed — no change (intentional)
- Declined `ormcache` on `is_on()` (marginal gain vs. cross-worker
  cache-coherency risk this repo has been bitten by).
- Kept the stored `name` post-create UPDATE (documented author trade-off;
  cost immaterial on a now-retention-bounded table).
- Kept the redundant single-column `os_memory` indexes (harmless).

### Verified clean (no defects)
Clean on all 11 v19-breakage axes, SQL-injection-free, no eval/exec, no
deprecated decorators, correct security model. See `REVIEW_REPORT.md`.
