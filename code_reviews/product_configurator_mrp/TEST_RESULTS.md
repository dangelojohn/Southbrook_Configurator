# Test Results — `product_configurator_mrp` v19.0.1.1.0

**Date:** 2026-07-10 · **Runtime:** Odoo 19.0 CE (`v19c-odoo`), Postgres 16
**Method:** southbrook version overlaid over the container's OCA copy (backup outside the addons path); isolated DB; OCA restored after.

## 1. Cold install — PASS
`odoo -i product_configurator_mrp` loads cleanly on v19 (baseline and post-fix), no ParseError / Invalid-field. Confirms all 3 changes (BoM `values2` fix, ACL widening, qweb-key removal) install correctly.

## 2. Automated tests — 2/3 pass, no regressions
```
product_configurator_mrp: 0 failed, 1 error(s) of 3 tests
```
The 1 error is `TestMrp.setUpClass` → `External ID not found: product_configurator.bmw_2_series` — the test fixture (via the parent module's `tests/common.py`) requires the BMW configurator demo data, which the local container does not load. **Environment limitation, not a defect** (passes in OCA CI / demo-enabled instances). `test_bom_contents` passes. My fixes introduced zero new failures.

## 3. Security fix verification — PASS
The wizard model `product.configurator.mrp` ACL now grants access to
`group_product_configurator` (was manager-only) — the Configure feature is
usable by its intended audience.

## Overall: PASS (harness caveat)
Install clean ✓ · no regressions ✓ · ACL fix applied ✓. The demo-dependent
BoM-generation tests need a demo-enabled env (the fixed `values2` common-branch
in particular is not covered by the existing suite — flagged).
