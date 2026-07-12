# Code Review — `southbrook_ai_design` (Module #21, Tier 4)

**Version:** 19.0.0.2.0 → **19.0.0.3.0**
**Reviewed:** 2026-07-11
**Scope:** ~767 LOC, no controllers — a Gemini-backed room-analysis service (`southbrook.gemini.client` AbstractModel calling Google's Gemini REST API → writes `sb.kitchen.ai.analysis`). Models: gemini client, `sb.gemini.prompt.template`, `sb.kitchen.project` extension; config params; prompt template. Depends: base, southbrook_kitchen_workspace.
**Method:** Two parallel audits (v19+code; security+perf) + live install/upgrade/test validation.

## Executive Summary
Both audits found the module **architecturally sound on the highest-value axes**: **no SSRF** (image read from an `ir.attachment`, not a URL; endpoint is a fixed Google constant), **no `eval`/`exec`** (response `json.loads`'d + a schema `_validate`), **no shipped secret** (`gemini.api_key` ships empty; `use_mock=True` default → zero API calls on a fresh install), the **GAP-02 `confirmed_by_human` gate is held** (client stamps `False` on every record — never auto-confirms), minimal data exfil (only the static prompt + image; no PII/pricing), and the prompt template is admin-write-only. v19-CLEAN install (lazy `httpx`, no `obj()` trap).

The one serious finding: an **API-key-leak-into-logs** via an uncaught `raise_for_status()` with the key in the URL query string. Fixed + hardened. Install + upgrade clean; **19/19 tests green** with a new regression test.

## Fixed
| # | Sev | Title | Fix |
|---|-----|-------|-----|
| H1 | HIGH (secret exposure) | Gemini API key in the URL query string (`?key=...`) leaked into logs/UI: `raise_for_status()` raises `httpx.HTTPStatusError` (whose text includes the request URL) for 400/404/5xx — NOT caught (only ConnectError/ReadTimeout were), so it propagated as a 500 with the key in the traceback/log | key moved to the `x-goog-api-key` **header** (never in the URL); `HTTPStatusError` now caught → clean key-free `UserError` |
| M2 | MEDIUM (DoS) | Unbounded server-controlled `Retry-After` `time.sleep` (+ synchronous 60s×4 blocking call) can wedge the small worker pool → 502s | `Retry-After` capped at `min(x, 30)` |
| M3 | MEDIUM (data-integrity) | `consume_gemini_analysis()` is a public ORM method that wrote the payload WITHOUT the validator (analyze()'s `_validate` bypassed on a direct call) | re-runs `_validate` at entry (idempotent → normal path unaffected) |
| L1 | LOW (UX/v19) | `get_by_code()` raised `ValueError` (→ 500) not `UserError`; unused `_` import | `UserError` (also uses `_`) |

## Documented (not applied)
- **M1 (MEDIUM, cost)** — no rate-limit/quota on `analyze_photo`: any `base.group_user` can loop the paid Gemini API (unbounded Google bill). Needs a per-user/day cooldown or a manager-gated action — a cost-policy owner decision.
- **M2 (full)** — offload the whole Gemini call to a queue_job/cron off the request path (the cap mitigates the worst case; full async is the real fix).
- **M3 (bounds)** — `_validate` doesn't bound `floor_area_m2_approx`/`window_count`/`room_door_count`; add plausibility ranges.
- **L1 image size** — cap max image bytes before base64/POST (worker-memory spike).
- **L2 dedup** — the idempotency lookup is an unindexed `ilike` substring scan on a Text column; store `image_hash` in a dedicated indexed `Char`.
- **L3** — batch the per-appliance `create`. **L4** — keep `raw_response_json`/model-supplied `label`/`notes` escaped if ever surfaced on the website (future stored-XSS). **L5** — `template.model` interpolated into the URL path (admin-only, low).

## Database / Security / Performance
- No schema changes. Key-in-logs leak closed (H1); worker-block DoS mitigated (M2); validator bypass closed (M3). Positive posture (no SSRF/eval/shipped-secret, gate held) preserved.

## Testing Results
- **Install + upgrade:** ✅ clean, v19-CLEAN (lazy httpx; `use_mock=True` → no network needed).
- **Unit tests:** ✅ **0 failed / 0 error / 19 tests** (install + upgrade).
- **New regression test:** `test_consume_revalidates_payload` — a wrong-schema payload passed to `consume_gemini_analysis` now raises `UserError` (guards the M3 bypass fix). Existing lander + validator tests all pass.

## Recommendations (priority)
1. **M1** — rate-limit / manager-gate `analyze_photo` (paid-API cost).
2. **M2 (full)** — move the Gemini call to a queue_job/cron.
3. **M3 (bounds)** + **L1/L2** — add dimension range checks, an image-size cap, and an indexed `image_hash` column.
