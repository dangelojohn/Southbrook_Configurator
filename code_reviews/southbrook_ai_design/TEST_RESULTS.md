# Test Results — `southbrook_ai_design` (Module #21)

**Harness:** v19c-odoo, isolated DB, staged with dep chain (southbrook_kitchen_workspace,
southbrook_estimating, southbrook_qr_kit) over the OCA modules.

## Install / upgrade
- Fresh install (`-i`): ✅ SUCCESS — v19-CLEAN. `httpx` is imported lazily (module
  loads without it); `gemini.use_mock=True` default → no network/key needed; no
  obj() trap (config params + prompt template are plain literal records).
- Upgrade (`-u`): ✅ SUCCESS.

## Unit tests
`--test-enable --test-tags southbrook_ai_design` → ✅ **0 failed / 0 error / 19 tests**
(install + upgrade).

### New regression test (passes)
- `test_consume_revalidates_payload` — a payload with a wrong `schema` passed
  directly to `consume_gemini_analysis()` now raises `UserError` (the method
  re-runs `_validate`, closing the validator-bypass — audit M3).

### Existing tests still green
The lander tests (`test_lander`: creates analysis + appliances, all-unconfirmed,
idempotent-by-image-hash, missing/non-dict payload rejection, analyze_photo mock
DoD) and the validator tests (`test_validator`) all pass — the added `_validate`
in `consume` is a no-op on the already-valid baseline payloads, and the key-header
/ error-sanitisation changes don't affect the mock backend path.

## Audit cross-checks
- v19+code: **CLEAN** — no install/registry issues; lazy httpx; all cross-module
  fields resolve against kitchen_workspace.
- Security: no SSRF (attachment image, fixed endpoint), no eval (json.loads +
  _validate), no shipped secret (empty key + mock default), `confirmed_by_human`
  gate held. The key-in-logs leak (H1, fixed) was the headline.

## Conclusion
A well-built AI service whose one serious flaw — a live Gemini API key leaking into
logs via an uncaught HTTP error — is closed (header + sanitised error), alongside a
Retry-After DoS cap and a validator-bypass fix. Install + upgrade clean, full suite
green. Cost-abuse rate-limiting and full async offload are documented for follow-up.
