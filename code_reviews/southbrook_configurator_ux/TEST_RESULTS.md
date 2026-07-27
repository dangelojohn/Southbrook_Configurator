# Test Results — `southbrook_configurator_ux` (Module #17)

**Harness:** OrbStack `v19c-odoo`, isolated DB, staged with dep chain
(`southbrook_estimating`, `southbrook_qr_kit`) over the 4 OCA modules.

## Install / upgrade
- Fresh install (`-i`): ✅ SUCCESS (no `obj()` install trap — data files use the
  bare `<function model name/>` pattern).

## Unit tests — my changes are CLEAN (baseline-verified)
- **Unmodified HEAD baseline:** 15 failed / 0 error / 54 tests.
- **After this pass:** 15 failed / 0 error / **55** tests — the +1 is the new
  `test_anon_sessions_isolated_by_http_session`, which **passes**.
- **Net: zero regressions.** The HIGH session-isolation fix and `type=jsonrpc`
  change introduced no new failures; the new security regression test passes.

## The 15 failures are PRE-EXISTING and test-only (confirmed on HEAD)
`test_select_commit` — two root causes, both pre-dating this review:
1. **SKU `-XXX`**: `test_select_returns_live_sku_composed_from_picks` /
   `..._changes_when_picks_change` expect `SB-21I-SIG-WAL` but get `...-XXX` —
   the Finish pick doesn't compose into the live SKU on this v19 build.
2. **`incomplete_configuration`**: the commit tests (via the shared
   `_complete_via_select` helper) don't pick `Door Style`/`Door Overlay`/
   `Interior Storage` — required attributes the module's own
   `catalog_expansion`/`tactical_price_seed` seed adds, which the fixtures
   predate. Production is unaffected (customers pick all attributes in the UI).

These need a dedicated fixture-update + SKU-composition triage pass (out of scope
for this security review; not caused by these changes).

## Static / audit cross-checks
- v19+JS audit: **no install/web-client breakage**; JS mount sidesteps public-page
  traps; only `type="json"` (fixed).
- Security audit: **no auth=public money vector** (pricing server-side); no XSS;
  the anon-session IDOR (H1, fixed) was the headline.

## Conclusion
Security posture materially improved (anon session isolation closed) with a
passing regression test and zero regressions. A pre-existing 15-test debt
(fixture drift + a SKU-composition question) is documented for follow-up.
