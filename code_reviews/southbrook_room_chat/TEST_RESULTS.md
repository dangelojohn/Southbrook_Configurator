# Test Results — `southbrook_room_chat`

**Date:** 2026-07-11
**DB:** `ci_room_chat` (isolated, on `v19c-db`; created via db-local socket to
sidestep an OrbStack ephemeral-port storm — see `southbrook_room_capture`
REVIEW_REPORT env note).
**Addons:** full southbrook dep stack staged into `/mnt/extra-addons`;
`southbrook_dims.py` in container PYTHONPATH.

## Install (`-i`)
```
odoo -c /tmp/ci_rchat.conf -i southbrook_room_chat \
  --test-enable --test-tags=southbrook_room_chat --stop-after-init --no-http
```
- Clean install, no ERROR/CRITICAL.
- `odoo.tests.result: 0 failed, 0 error(s) of 47 tests`.

## Upgrade (`-u`)
```
odoo -c /tmp/ci_rchat.conf -u southbrook_room_chat \
  --test-enable --test-tags=southbrook_room_chat --stop-after-init --no-http
```
- Registry loaded 1.7 s — **0 failed, 0 error(s) of 47 tests**. Idempotent.

## New regression tests (all green)
| Test | Asserts |
|------|---------|
| `test_handle_turn_is_not_rpc_dispatchable` | public `handle_turn` gone; `_handle_turn` exists (H2) |
| `test_daily_cap_kill_switch_blocks_real_call` | `max_daily_calls=0` → `rate_limited`, `_call_anthropic` never called |
| `test_daily_cap_reached_blocks_further_turns` | 1st turn OK; next → `rate_limited` |
| `test_daily_cap_counts_per_real_call_not_per_turn` | 1-cap stops a fan-out turn after its 1st call; draft still built |
| `test_daily_cap_does_not_apply_to_mock` | mock backend never consumes quota |

## Pre-existing suite (unchanged, all green)
- `TestRoomChatSession` — get-or-create singleton, blank-draft shape, draft/
  transcript roundtrip, reset, `UNIQUE(order_id)`, race-safe create.
- `TestRoomChatAgentModel` — mock tool loop (real executor), draft population/
  persistence, reset, message validation, every tool's input validation
  (shape/enum/index-bounds/distance/heights), `validate_current_draft`, no-room-
  records, real-path tool loop via mocked transport, malformed/failed/refusal
  recovery, not-configured-without-key.
- `TestRoomChatController` — authenticated access, **ownership rejection for
  non-owning portal user** (confirms the controller gate still holds after the
  H2 rename), empty/missing message, no-room-records end-to-end, **rate limit
  enforced**, reset without message.

**Total: 47/47 pass on both `-i` and `-u`. No regressions.**

## Notes
- `WARNING … Anthropic call failed: Anthropic HTTP 503` is an **intended** test
  assertion (`test_failed_ai_call_graceful`), not a real failure.
