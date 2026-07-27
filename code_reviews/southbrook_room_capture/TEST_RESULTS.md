# Test Results — `southbrook_room_capture`

**Date:** 2026-07-11
**DB:** `ci_room_capture` (isolated, on `v19c-db`)
**Addons:** full southbrook dep stack staged into `/mnt/extra-addons`;
`southbrook_dims.py` in container PYTHONPATH.

## Install (`-i`)
```
odoo -c /tmp/ci_rc.conf -i southbrook_room_capture \
  --test-enable --test-tags=southbrook_room_capture --stop-after-init --no-http
```
- Registry loaded in **37.3 s** — no ERROR/CRITICAL.
- `southbrook_room_capture: 54 tests 0.46s` /
  `46 post-install tests` → **0 failed, 0 error(s)**.

## Upgrade (`-u`)
```
odoo -c /tmp/ci_rc.conf -u southbrook_room_capture \
  --test-enable --test-tags=southbrook_room_capture --stop-after-init --no-http
```
- Registry loaded in 1.7 s — **0 failed, 0 error(s) of 46 tests**. Idempotent.

## New regression tests (all green)
| Test | Asserts |
|------|---------|
| `test_daily_cap_kill_switch_blocks_real_call` | `max_daily_calls=0` → `rate_limited`, `_call_anthropic` never invoked |
| `test_daily_cap_reached_blocks_further_real_calls` | 1st real call OK within cap; 2nd → `rate_limited` |
| `test_daily_cap_does_not_apply_to_mock` | mock backend never consumes quota |

## Pre-existing suite (unchanged, all green)
- `TestRoomCaptureModel` — mock short-circuit, real-path JSON parse/normalize,
  upload validation, malformed/failed/refusal/max_tokens recovery, low-confidence
  flagging, geometry-gated-by-validate_geometry, no-ir.attachment privacy.
- `TestRoomCaptureController` — auth access, ownership rejection, upload
  validation, no side-effects, existing_room payload shape.
- `TestQrPartModel` / `TestScanPartController` — signed/legacy payload resolve,
  bad-signature/wrong-kind/out-of-range rejection, ownership rejection, customer-
  safe serialization, no-records-created.

**Total: 46/46 post-install tests pass on both `-i` and `-u`. No regressions.**

## Notes
- `WARNING … Anthropic call failed: Anthropic HTTP 503` is an **intended** test
  assertion (`test_failed_ai_call_graceful`), not a real failure.
- `<string>:24: (ERROR/3) Unexpected indentation` is a cosmetic docutils RST
  warning on a manifest `description`, unrelated to this module's code.
- The OrbStack VM's transient ephemeral-port (`TIME_WAIT`) exhaustion required
  creating the DB via the db container's local socket; see REVIEW_REPORT.md.
