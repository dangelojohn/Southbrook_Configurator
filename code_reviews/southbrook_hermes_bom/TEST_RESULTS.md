# Test Results — `southbrook_hermes_bom` v19.0.2.4.0

**Date:** 2026-07-10 · **Runtime:** Odoo 19.0 CE (`v19c-odoo`), Postgres 16
**Method:** module staged into container addons; isolated DB; unstaged after.

## 0. Baseline — GREEN
As-shipped: `0 failed, 0 error(s) of 26 tests`. Tests use demo-mode (no external
call, no bmw-demo dependency) — a healthy starting point.

## 1. Cold install — PASS
`odoo -i southbrook_hermes_bom` loads cleanly on v19; all data/security/views/
cron load; the 2 new indexes (`product_template_id`, `state`) applied.

## 2. Automated tests — PASS (28 tests, 0 failed, 0 errors)
```
southbrook_hermes_bom: 0 failed, 0 error(s) of 28 tests
```
26 pre-existing + the new `TestHermesSsrfGuard` (blocks cloud-metadata/loopback/
private/non-http hosts; allows a public IP). During development one iteration of
the SSRF test failed because the guard checked IP-safety but not scheme — the
guard was tightened to also require http/https (the security boundary), after
which the suite is fully green. No regressions to the existing 26.

## 3. Fix verification
- `_is_safe_public_url` blocks `169.254.169.254`, `127.0.0.1`, `localhost`,
  RFC1918, and non-http(s) schemes (test-verified); `allow_redirects=False`.
- `_validate_response` type-checks nested sections; `_apply_bom` has isinstance
  guards.
- 2 indexes on `hermes.research.job` created on install.

## Overall: PASS
Install clean ✓ · 28/28 tests green (from 26) ✓ · SSRF guard test-verified ✓ ·
response-validation hardened ✓ · indexes applied ✓.
