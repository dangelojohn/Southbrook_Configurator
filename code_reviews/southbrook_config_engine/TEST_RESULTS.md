# Test Results — `southbrook_config_engine` (Module #20)

**Harness:** v19c-odoo, isolated DB, staged with dep chain (southbrook_kitchen_workspace,
southbrook_estimating, southbrook_hardware_catalog, southbrook_qr_kit) over the OCA modules.

## Install / upgrade
- Fresh install (`-i`): ✅ SUCCESS — v19-CLEAN (no obj() trap; placement_rules.xml uses
  plain literal `<field>` values; all cross-module dependency fields resolve).
- Upgrade (`-u`): ✅ SUCCESS.

## Unit tests
`--test-enable --test-tags southbrook_config_engine` → ✅ **0 failed / 0 error / 18 tests**
(install + upgrade). The whole suite completes in **0.11s**.

### New regression tests (all pass)
- `test_no_exact_fit_float_gap_terminates_fast` — packs a 4212.5mm gap (not a
  multiple of 25 → no exact fit). PRE-FIX this alone was ~292M recursive calls /
  a multi-second hang; the suite would have timed out. Now instant.
- `test_zero_width_does_not_infinite_recurse` — a width of 0 is filtered, not
  recursed on forever.
- `test_bad_width_pref_rule_rejected_at_save` — a `{"preferred_widths_mm":[0]}`
  and a `{"left_mm":"abc"}` rule each raise ValidationError at create.

### Existing tests still green
The GAP-02 gate tests (`test_gap02_gate`), the 5 layout topologies + determinism
(`test_layouts`), and the packing primitives (`test_pack_stretch`) all pass — the
memoised packer returns the same first-fit plan, and the "blank = all" fix doesn't
affect the seeded rules (which set all scope fields explicitly).

## Audit cross-checks
- v19+code: **CLEAN** — no install/registry issues.
- Security: no eval/injection (JSON rules), GAP-02 gate enforced server-side + not
  RPC-bypassable, zero sudo, complete/manager-scoped ACL, no N+1, output is a
  preview blob (no money/BoM write). The CRITICAL was the packer DoS (fixed).

## Conclusion
A clean, well-designed engine whose one serious flaw — an exponential packer that
DoS'd the worker on most real placements — is fixed (memoised DP, identical output)
and guarded by a fast-terminating regression test, alongside rule-payload hardening
and a "blank = all" correctness fix. Install + upgrade clean, full suite green.
