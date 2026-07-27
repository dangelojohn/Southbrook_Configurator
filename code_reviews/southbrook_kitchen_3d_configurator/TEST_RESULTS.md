# Test Results — `southbrook_kitchen_3d_configurator` (Module #16)

**Harness:** OrbStack `v19c-odoo`, isolated throwaway DB, staged with dep chain
(`southbrook_estimating`, `southbrook_qr_kit`) over the 4 OCA modules. Never prod.

## Install / upgrade
- **Baseline (before this pass): INSTALL FAILED** — `Failed to load registry`
  at `security/groups.xml:47` (`NameError: name 'obj' is not defined`). The
  module could not be installed on this v19 CE build at all.
- **After the C1 fix — fresh install** (`-i`): ✅ SUCCESS.
- **Upgrade** (`-u`): ✅ SUCCESS.

## Unit tests
`--test-enable --test-tags southbrook_kitchen_3d_configurator` → ✅ **0 failed, 0 error(s) of 28 tests** (36 incl. subtests), install + upgrade.

### Iteration (documents the validation catching real issues)
1. First install after C1: **1 error** — `test_06_savepoint_wraps_action_confirm`
   → `ValueError: Invalid field 'force_production_release' in 'sale.order'`.
   Traced to `kitchen_design.py:1264` writing a field defined only in
   `southbrook_mrp_pm` (Tier 5). Fixed with a `in order._fields` guard (H3) —
   the module can't hard-depend on Tier 5.
2. After H3: **0 failed, 0 errors**.

### New regression test (passes)
- `test_07_client_price_is_ignored_server_reprices` — posts `save_design` with an
  attacker-chosen `price: 1.00`; asserts the persisted design line's `price_unit`
  is NOT 1.00 and equals the server-computed catalog price. Guards the H1 money
  vector; would fail on the pre-fix code.

### Pre-existing tests still green
All `test_save_design_acl` (catalog-contract enforcement — still holds with the
batched search + reprice), `test_m1_m2_reconcile_fixes`, and the `test_track_b`
BoM-autoseed suite pass.

## Static / cross-checks
- `python3 -m py_compile` on all changed Python + XML well-formedness: ✅
- v19+JS audit: JS/OWL surface **CLEAN** (correct `rpc`/`user` imports; backend
  client action, not a public mount). Only v19 item was `type="json"` (fixed).
- Security audit: **no `auth="public"` routes**; the money-vector (H1), IDOR (M1),
  and isolation-policy (D1) were the findings.
- **The CRITICAL install-blocker (C1) was found by neither audit agent — only by
  running the install.** Both agents verified `groups.xml` field names but not
  that `obj()` is unavailable in a `<value>`-child eval context on this build.

## Conclusion
A large, otherwise well-hardened module that **did not install on current v19 CE**
until this pass. Install + upgrade now clean; the customer-facing price vector is
closed and guarded; the cross-tier field crash is guarded. Full suite green.
Per-designer isolation (D1) remains a documented owner decision.
