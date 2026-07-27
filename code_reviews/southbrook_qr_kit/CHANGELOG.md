# Changelog — `southbrook_qr_kit`

## 19.0.0.15.0 — 2026-07-10 (code review #2)

Correctness, security, and performance repairs. The module shipped with a red
test suite (15/57 failing) and a non-functional QR dispatch in prod; this
release restores it to 60/60 green and closes three CRITICAL security issues.

### Fixed — correctness
- **Kind dispatch (CRITICAL, prod-breaking):** `resolve_kind` returns a *falsy*
  empty AbstractModel recordset on a hit; callers now test the `False`
  sentinel (`if handler is False:`) instead of truthiness, so scans/POD/floor/
  trolley ops no longer all return `unknown_kind`. (`qr_scan.py`,
  `floor_action.py`, + test.)
- **Trolley bind crash:** guarded workorder `message_post` with `hasattr`
  (`mrp.workorder` has no `mail.thread` in base v19 CE).
- **Floor shell served empty page:** `_render_floor_shell` now `flatten()`s the
  lazy QWeb response before reading/rewriting the body.
- **Dead redirects:** `/odoo/action-<model>/<id>` → `/odoo/<model>/<id>` in
  `scan_get` and `qr_kind.handle_action`.

### Fixed — security
- **Reflected XSS (CRITICAL)** in `scan_get`: all interpolated values escaped.
- **Query-smuggling XSS (CRITICAL):** `parse()` rejects query keys other than
  `t`/`s`, closing unsigned-content injection into public POD/floor pages;
  inline-`<script>` payload embedding switched from `repr()` to `</`-safe
  `json.dumps()`.
- **PIN brute-force (CRITICAL):** per-IP failed-attempt throttle (5 / 5 min) on
  `/sb/qr/identify`.
- **Stock ACL bypass (HIGH):** removed `.sudo()` from `bin_scan`.
- **Stored XSS (HIGH):** `display_name` escaped in `/sb/qr/labels`.

### Changed — v19 modernisation
- `check_access_rights()`/`check_access_rule()` → `check_access("read")`.
- All `@route(type="json")` → `type="jsonrpc")` (deprecation warnings removed).

### Added — performance
- Indexes on scan-log `target_model`, `target_id`, `create_date`.
- Scan-log retention: `autovacuum()` + daily `ir_cron_qr_scan_log_prune`
  (`southbrook.qr_kit.scan_log_retention_days`, default 180; `<=0` = keep).
- `/sb/qr/labels` caps `ids` at 200.

### Added — tests
- `tests/test_security_hardening.py` (query-key rejection + PIN throttle).
- Fixed the w072 (`_FakeResponse`→werkzeug `Response`) and w071 (conditional
  workorder chatter) harnesses for v19.

### Verified sound (no change)
HMAC crypto (constant-time `compare_digest`, CSPRNG secret, never logged),
scan-log append-only ACL, no SQL injection, no eval/exec. See `REVIEW_REPORT.md`.
