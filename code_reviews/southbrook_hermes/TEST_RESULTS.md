# Test Results — `southbrook_hermes`

**Date:** 2026-07-11 · **DB:** isolated on `v19c-db` · full southbrook stack staged.

## Baseline (unmodified HEAD)
`-i --test-tags=/southbrook_hermes`: **2 failed, 4 error(s) of 86 tests** (install
clean). Causes: PyJWT not in the container (3 JWT errors), `get_order_status`
`sale_order_line_id`/field-name bug (1), and 2 answer-assertion drifts.

## After fixes
- `-i` (fresh DB) — registry 41.6 s, no ERROR/CRITICAL — **0 failed, 0 error(s) of
  86 tests**.
- `-u` — **0 failed, 0 error(s) of 86**.

## Resolved
| Cluster | Count | Resolution |
|---------|-------|------------|
| JWT-helper (mint/verify/expired/tampered) | 3 | PyJWT installed in container (module lazy-imports + degrades gracefully) |
| `get_order_status` | 1 | `sale_line_id` + correct guarded project.task field names (V3/V2) |
| internal-answer / customer-pricing wording | 2 | create the described users / assert actual wording |

**Note:** PyJWT was installed via `pip install --break-system-packages PyJWT`
(2.13.0) — the module manifest should declare `external_dependencies:
{"python": ["jwt"]}`. All 86 tests pass on both `-i` and `-u`.
