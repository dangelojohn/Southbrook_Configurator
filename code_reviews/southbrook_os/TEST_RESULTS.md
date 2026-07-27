# Test Results — `southbrook_os` (Module #12)

**Harness:** OrbStack `v19c-odoo`, isolated throwaway DB, `--without-demo=all`,
HTTP enabled on port 8299 (the public-endpoint tests are `HttpCase`), staged
`southbrook_os` + dep chain (`southbrook_estimating`, `southbrook_qr_kit`) over the
4 OCA modules. Never run against prod/QNAP.

## Baseline (unmodified HEAD, for regression proof)
`-i southbrook_os --test-enable --test-tags southbrook_os` → **2 failed, 7 error(s) of 25 tests.**
All 9 were pre-existing: 7× `UniqueViolation` (tests' `setUp` re-creating canonical
slugs that post_init loads), 1× `<h1>` (optional `markdown` package absent), 1×
cut-spec (needs `southbrook.cut.spec` from `southbrook_plm`).

## After this pass
- **Fresh install** (`-i`): ✅ SUCCESS. All new logic loads (audience-filtered
  controller, cron/post_init publish, sanitised `body_html`, loader refresh, index).
- **Upgrade** (`-u`): ✅ SUCCESS.
- **Unit tests** (`-i` and `-u`): ✅ **0 failed, 0 error(s) of 26 tests.**

Net change: +1 test (the public-endpoint suite went 2→3), the 2 new security
regression tests pass, and every previously-failing test now passes via
test-isolation/optional-dependency fixes — **zero production regressions**
(production-code changes are the security/idempotency fixes; the test-only edits
don't alter shipped behaviour).

### Security regression tests (new)
- `test_os_json_returns_only_public_sections` — asserts `00_charter` is served,
  asserts `20_systems_topology`/`01_company`/`02_catalog`/`05_production`/`06_plm`
  are NOT, and asserts every served section is `public`-tagged. **This fails on the
  vulnerable baseline** (which leaks all sections) and passes on the fix.
- `test_public_get_does_not_write_publications` — asserts two anonymous GETs create
  no publication rows (read-only route).

## Static checks
- `python3 -m py_compile` on all changed models/controllers/exports/tests: ✅
- v19-compat audit: module confirmed CLEAN (models.Constraint, v19 cron schema,
  `post_init(env)`, `yaml.safe_load`, `@api.model_create_multi`, `env.get()` model
  probing) — no v19 breakages.

## Conclusion
Production code is v19-clean and now secure at the public boundary. Install +
upgrade clean; full suite green. The public data-exposure and unauthenticated-write
holes are closed and guarded by regression tests. Three deeper items (D1 live-vs-
snapshot, D2 OSRO SoD, D3 retention) are documented owner/design decisions.
