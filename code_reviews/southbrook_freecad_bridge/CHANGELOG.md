# CHANGELOG — `southbrook_freecad_bridge`

## 19.0.0.5.0 — 2026-07-11 — Code-review pass (Module #19)

### Security
- **[HIGH] Constant-time bridge-secret comparison** (`hmac.compare_digest`) —
  was a plain `!=` (timing side-channel). `controllers/main.py`.
- **[HIGH, partial] Callback attachment link is now `(4,id)` ADD, not `(6,0)`
  REPLACE** — a forged/replayed call can no longer wipe the linked CAD
  artifacts. (Full fix — restrict ids to attachments bound to the MO — needs the
  bridge upload flow confirmed; documented.) `controllers/main.py`.
- **[MEDIUM] Callback state guard** — only accepts a callback for an MO awaiting
  a render (pending/rendering) or an idempotent same-status replay; else 409.
  Blocks forged/replayed regressions across the factory. `controllers/main.py`.
- **[MEDIUM] Input validation** — `int()` coercions → 400 (was uncaught 500);
  `attachment_ids` capped at 200. `controllers/main.py`.

### Fixed (v19 / hygiene)
- `mail.mt_log_note` → `mail.mt_note` (the former doesn't exist in v19; worked
  only via fallback). `models/mrp_production.py`.
- Secret mismatch now returns the documented JSON 401 (was a raised AccessError
  → 403 HTML). `controllers/main.py`.

### Tests
- Added `test_forged_regression_of_settled_mo_is_blocked` (409) and
  `test_idempotent_replay_of_same_status_allowed` (200). Both pass; all existing
  callback/auth/gate tests pass.

### Notes (documented, not changed)
- Full HIGH-2 (attachment ownership filter) pending the bridge's upload/bind flow.
- Outbound render POST blocks the confirm transaction (10s×N) — move to
  after_commit/queue_job (MEDIUM-2).
- Pre-existing: `southbrook_dims` ↔ estimating TOEKICK_FAMILIES parity drift
  (test_bom_contents) + dims_js_parity harness path — unrelated to these changes.
