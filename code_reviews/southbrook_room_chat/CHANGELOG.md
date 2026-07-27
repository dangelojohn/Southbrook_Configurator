# Changelog — `southbrook_room_chat`

## 19.0.2.3.0 — 2026-07-11 (code-review pass, module #26)

### Security — Fixed

- **H2 (HIGH) — IDOR / ownership + rate-limit + spend bypass.** Renamed the public
  `southbrook.room.chat.agent.handle_turn` → **`_handle_turn`** so it is **no longer
  RPC-dispatchable** via `call_kw`. It sudo-reads/writes the session for `order_id`
  without its own ownership check, trusting its sole caller (the controller) to have
  resolved the order against the acting user and enforced the rate limit. As a public
  method any authenticated portal user could call it directly against an arbitrary
  `order_id`, bypassing both gates. `controllers/main.py` now calls `_handle_turn`.
- **H1 (HIGH) — global daily spend cap + kill-switch** on the paid Anthropic path
  (the module reused `southbrook_room_capture`'s API key but had no cap):
  - `_daily_cap()` — reads `ir.config_parameter southbrook_room_chat.max_daily_calls`
    (default `1000`).
  - `_consume_daily_quota()` — increments a per-day counter
    (`…daily_call_date`/`…daily_call_count`); returns `False` at the cap.
    **`max_daily_calls = 0` = hard kill-switch.**
  - Counted **per real `_call_anthropic` call** (each turn fans out up to
    `_MAX_TOOL_ITERATIONS` calls). Over-cap on the turn's first call →
    `{"error": "rate_limited"}`; mid-turn → the loop stops gracefully and persists
    the draft built so far. The **mock** backend is never gated.
  - `from odoo import … fields …` added for the per-day date stamp.

### v19 — Fixed
- `type="json"` → `type="jsonrpc"` on the chat route + docstring
  (`controllers/main.py:9,92`).

### Tests
- `test_handle_turn_is_not_rpc_dispatchable` — asserts `handle_turn` is gone and
  `_handle_turn` exists (H2 regression).
- `test_daily_cap_kill_switch_blocks_real_call` — `max_daily_calls=0` →
  `rate_limited`, `_call_anthropic` never called.
- `test_daily_cap_reached_blocks_further_turns` — 1st turn OK; next → `rate_limited`.
- `test_daily_cap_counts_per_real_call_not_per_turn` — a 1-cap stops a fan-out turn
  after its first call (draft still built, 2nd call never made).
- `test_daily_cap_does_not_apply_to_mock` — mock backend ignores the cap.
- All existing `.handle_turn(` call sites updated to `._handle_turn(`.

### Not changed (documented in REVIEW_REPORT.md)
- M1 lead/order pinning to a guessed existing partner (identity-trust policy),
  M2 per-user lead cap, M3 async offload of the sync call (infra), M4 PII record-rule
  scoping (access-model), R1 shared-store rate limiter. No change to the tool loop,
  geometry contract, CRM description building, or the front-end.
