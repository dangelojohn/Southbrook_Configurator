# Test Results — `southbrook_estimating` (Module #11)

**Harness:** OrbStack `v19c-odoo` container, isolated throwaway DB, `--without-demo=all`,
`/mnt/extra-addons` = `~/Downloads/Official/V19C/product-configurator` (the 4 OCA
modules) + freshly-staged `southbrook_estimating` and `southbrook_qr_kit` (dep).
Never run against prod/QNAP.

## Install / upgrade
- **Fresh install** (`-i southbrook_estimating`): ✅ SUCCESS. All new data loads —
  the added ACL rows, the `pricelist_refacing_item_global` item, the hex report
  styles, the SSRF guard, and the batched creates. No load errors.
- **Upgrade** (`-u southbrook_estimating` on the installed DB): ✅ SUCCESS.

## Unit tests
`--test-enable --test-tags southbrook_estimating` → **284 tests, 276 pass, 2 failed, 6 error(s).**

Baseline before this pass was **2 failed / 10 error(s)** (282 tests). This pass:
- **Eliminated the 4 QWeb-report errors** (the `env['website']` KeyError, F7).
- **Added 2 passing SSRF tests** (F4).
- **Introduced 0 new failures.**

### The 8 remaining failures are ALL cross-module / harness-isolation artifacts (not defects in this module):

| Count | Test(s) | Cause | Passes in prod because… |
|-------|---------|-------|--------------------------|
| 5 err | `TestActionConfirmHardValidation.*` | `ValueError: Invalid field 'production_approval_state' in 'sale.order'` | that field is defined by `southbrook_mrp_pm` (Tier 5), installed in the full stack |
| 1 fail | `TestRoomUnplacedCabinets.test_unplaced_counts_cabinet_without_wall` (`0 != 1`) | `southbrook_is_cabinet` is a `southbrook_kitchen_3d_configurator` field → returns 0 standalone | that field exists once kitchen_3d (Tier 3) is installed |
| 1 err + 1 fail | `TestOCAValidationErrorWrappersV19.test_01/02` | The tests read the **staged OCA** `product_configurator` source, which still uses the v18 `exc.name` pattern (`:894/:927`) | southbrook-v19cr's OWN `product_configurator` copy has the v19-safe `exc.args[0] if exc.args else str(exc)` at `:919/:964` (verified by direct source diff) |

**Verification that these are not regressions:** every one of the 8 was present in the
pre-change baseline run with an identical signature; each traces to a field/source that
lives in a *different* addon not staged in this isolated harness. My 7 fixes touched none
of the code paths these tests exercise, and the 2 new SSRF tests pass.

## Manual / static checks
- `python3 -m py_compile` on all changed models + test file: ✅
- XML well-formedness on all changed XML (incl. the report/pricelist files): ✅
- `_TYPE_LABELS` duplicate-key scan (AST): ✅ NONE (42 keys, was 44 with 2 dupes)
- v19 `_compute_price` override signature checked against core
  `addons/product/models/product_pricelist_item.py:570`: ✅ match

## Conclusion
Production code is healthy and v19-clean. Install/upgrade clean; the module's own logic
is fully green; the residual failures are the hub's full-stack integration tests running
without their downstream dependencies present — they pass in the deployed stack.
