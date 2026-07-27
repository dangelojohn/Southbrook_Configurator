# Changelog — `southbrook_room_capture`

## 19.0.3.1.0 — 2026-07-11 (code-review pass, module #25)

### Fixed
- **v19 deprecation:** `type="json"` → `type="jsonrpc"` on all 3 JSON-RPC routes
  and the module docstring (`controllers/main.py`). The v19 alias only warns, but
  the corrected form ships to prod (deploys rsync the working tree).

### Added — cost-abuse mitigation (security HIGH F2)
- **Global daily Anthropic-call cap + kill-switch**, shared across all workers,
  bounding the paid-API blast radius that the per-worker rate limiter cannot:
  - `southbrook.room.capture._room_capture_daily_cap()` — reads
    `ir.config_parameter southbrook_room_capture.max_daily_calls` (default `500`).
  - `southbrook.room.capture._room_capture_consume_daily_quota()` — increments a
    per-day counter (`…daily_call_date` / `…daily_call_count`) and returns `False`
    once the cap is hit. **`max_daily_calls = 0` is a hard kill-switch** — no real
    call is ever made.
  - `analyze()` now calls `_room_capture_consume_daily_quota()` **after** the
    API-key check and **before** `_call_anthropic`; over-cap → graceful
    `{"ok": False, "error": "rate_limited", …}`. The **mock** backend is never
    gated (free).
  - `from odoo import … fields …` added for the per-day date stamp.

### Tests
- `test_daily_cap_kill_switch_blocks_real_call` — `max_daily_calls=0` returns
  `rate_limited` and never reaches `_call_anthropic`.
- `test_daily_cap_reached_blocks_further_real_calls` — first real call within cap
  succeeds; the next is `rate_limited`.
- `test_daily_cap_does_not_apply_to_mock` — mock backend ignores the cap.

### Not changed (documented in REVIEW_REPORT.md)
- R1 shared-store rate limiter, R2 async offload of the 60 s call (both infra),
  R3 auto-lead gating, R4 QR TTL, R5 base64-before-cap. No behavioural change to
  the AI path, QR resolution, geometry normalization, or any front-end.
