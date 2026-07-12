# Test Results — `southbrook_kitchen_mrp` (Module #22)

**Harness:** v19c-odoo, isolated DB, staged with dep chain (southbrook_estimating,
southbrook_hardware_catalog, southbrook_freecad_bridge, southbrook_plm,
southbrook_qr_kit) over the OCA modules. `southbrook_dims.py` present in the
container PYTHONPATH (from Module #19) — required by `sb_production_package.py`'s
top-level import.

## Install / upgrade
- Fresh install (`-i`): ✅ SUCCESS. v19-CLEAN (no obj() trap; cron v19-schema; the
  new ir.sequence data loads; label report is hex-only CSS + t-out).
- Upgrade (`-u`): ✅ SUCCESS.

## Unit tests — HIGH fixed, zero regressions (baseline-verified)
- **Unmodified HEAD baseline:** 1 failed / **1 error** / 39 tests.
  - the ERROR was `test_label_renders_without_rev_when_unstamped` — the `hasattr`
    QWeb crash (the HIGH bug), which meant the label render was never validated.
- **After this pass:** 1 failed / **0 error** / 39 tests (install + upgrade).
  - The label test now **PASSES**: the render succeeds and correctly omits the
    Rev row for an unstamped MO (the `hasattr`→`in o._fields` fix + the corrected
    assertion). ERROR→PASS.
- **Net: the HIGH label crash is fixed; zero regressions.**

## The 1 remaining failure is PRE-EXISTING (confirmed on HEAD)
`test_build_from_order_line.test_emits_exactly_one_package_with_non_empty_cutlist`
— the cutlist is empty because `southbrook_dims.panel_cut_list` returns no panels
for the test cabinet on this build (a shared-dims data/version artifact, same
class as the freecad-bridge TOEKICK_FAMILIES parity drift). Identical on HEAD; I
touched none of `southbrook_dims`, `sb_cutlist`'s panel math, or that test.

## Audit cross-checks
- v19+code: install-CLEAN; the only serious item was the label `hasattr` (fixed).
- Security: well-defended — nesting I/O dict-only (no SSRF/eval), BoM cron
  private/idempotent/non-destructive, QR HMAC-signed + ACL-gated, no eval/SQL/XSS,
  ACL complete, hardware resolve() batched, FK indexing complete.

## Conclusion
A robust MRP module whose one feature-breaking bug — a label PDF that crashed on
every print — is fixed and now validated by a passing render test, alongside the
missing sequences, a graceful cross-module QR guard, and nesting-scrap logging.
Install + upgrade clean; the single remaining failure is a pre-existing shared-dims
data artifact.
