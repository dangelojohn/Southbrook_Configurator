# CHANGELOG — `southbrook_ai_design`

## 19.0.0.3.0 — 2026-07-11 — Code-review pass (Module #21)

### Security
- **[HIGH] Gemini API key no longer leaks into logs.** The key moved from the
  URL query string (`?key=...`) to the `x-goog-api-key` header, and
  `httpx.HTTPStatusError` (from `raise_for_status()` on 400/404/5xx — previously
  uncaught, propagating a 500 with the key-bearing URL in the traceback/log) is
  now caught and re-raised as a clean, key-free `UserError`.
  `models/southbrook_gemini_client.py`.
- **[MEDIUM] Capped `Retry-After`** at 30s — an unbounded/hostile value would
  block the request worker arbitrarily (→ 502s). `models/southbrook_gemini_client.py`.
- **[MEDIUM] `consume_gemini_analysis` re-validates the payload.** It's a public
  ORM method that previously bypassed `analyze()`'s `_validate`, so a direct
  caller could land unclamped/hallucinated dimensions. `_validate` is idempotent,
  so the normal path is unaffected. `models/sb_kitchen_project.py`.

### Fixed
- **[LOW] `get_by_code()` raises `UserError`** (was `ValueError` → opaque 500) on a
  missing/inactive template. `models/sb_gemini_prompt_template.py`.

### Tests
- Added `test_consume_revalidates_payload` (M3 regression). **19/19 green.**

### Notes (documented, not changed)
- No rate-limit on the paid `analyze_photo` (M1); the Gemini call is still
  synchronous on the request path (M2 full = queue-offload); `_validate` lacks
  floor-area/count bounds (M3); image size uncapped (L1); dedup is an unindexed
  ilike scan (L2). No SSRF, no shipped secret, no eval, GAP-02 gate intact.
