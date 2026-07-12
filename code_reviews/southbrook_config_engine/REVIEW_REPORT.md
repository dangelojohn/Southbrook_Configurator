# Code Review — `southbrook_config_engine` (Module #20, Tier 4)

**Version:** 19.0.0.1.0 → **19.0.0.2.0**
**Reviewed:** 2026-07-11
**Scope:** ~777 LOC, no controllers, no JS — the cabinet-placement rules engine (`southbrook.config.engine` AbstractModel + `sb.placement.rule` data-driven rules). Depends: southbrook_kitchen_workspace, southbrook_estimating, southbrook_hardware_catalog.
**Method:** Two parallel audits (v19+code; security+perf) + live install/upgrade/test validation.

## Executive Summary
A well-built, data-driven placement engine. Both audits confirmed strong foundations: **v19-CLEAN install** (no `obj()` trap, all cross-module fields resolve), **no code-injection** (rules are JSON payloads via `json.loads`, zero `eval`/`exec`/`safe_eval`), **GAP-02 AI-confirmation gate correctly enforced server-side** at the sole RPC entry (private helpers unreachable), **zero `sudo()`**, complete ACL with manager-only rule writes, and **no N+1** (rules loaded once, matched in memory).

The headline was a **CRITICAL performance/DoS**: an exponential-time packer that fires on ~92% of real placements. Fixed (memoised DP) + hardened rule validation + a correctness fix. Install + upgrade clean; **18/18 tests green** (suite runs in 0.11s, proving the fix) with 4 new regression tests.

## Fixed
| # | Sev | Title | Fix |
|---|-----|-------|-----|
| P1 | **CRITICAL** (perf/DoS) | `_greedy_pack` exponential-time when no exact ±1mm partition (the common case: widths are ×25, gaps are arbitrary floats) — a 4.2m gap measured ~292M recursive calls (multi-second worker hang) on nearly every placement | memoised on `round(length_mm)` (the fractional part is invariant under integer-width subtraction → collision-free key) → pseudo-polynomial DP returning the identical first-fit plan |
| S4 | MEDIUM (data-integrity) | Semantically-bad rule accepted at save → runtime 500 / infinite recursion later. `{"preferred_widths_mm":[0]}` → infinite recursion; `{"left_mm":"abc"}` → `float-str` TypeError 500 | `_check_constraint_json` now validates per-kind (positive numeric widths, non-negative numeric clearances; bool excluded) → clean `ValidationError` at write time; packer also filters non-positive widths |
| L1 | LOW (correctness) | "blank = all" rule scope was dead — `if r["appliance_kind"] != app["kind"]: continue` made a blank-scoped rule match NOTHING (contradicting the field help); same for width-pref theme | `if r["appliance_kind"] and ...` / `if not r["theme"] or r["theme"] == theme` (mirrors the already-correct clearance-theme check) |

## Documented (not applied)
- **S3 (MEDIUM, governance)** — placement rules drive *production* cuts (clearances), yet write authority is `sales_team.group_sale_manager` (Sales), not an engineering/manufacturing role. A sales manager could change a stove clearance 30mm→0mm and silently alter every future cut. Consider a dedicated engineering group (owner decision; no such group may exist yet).
- **S2 (LOW)** — the GAP-02 gate is flag-based (`confirmed_by_human`), not content-hash-based: room geometry is read from `ai_analysis_id.raw_response_json`, and if that raw JSON is mutated after confirmation without clearing the flag, stale geometry flows through. Owned by `southbrook_kitchen_workspace`; flagged for that owner.
- **P3 (LOW)** — `raw_response_json` is `json.loads`'d twice (`_read_room` + `_read_appliances`); parse once.
- **LOW-2** — appliances absent from the AI raw JSON are silently dropped (no warning) on a name mismatch; add an observability log.

## Database / Security / Performance
- No schema changes. Placement output is an opaque `placement_data_json` preview blob — writes NO prices/positions to sale.order.line or kitchen.design.line (good containment). GAP-02 gate + no-eval + no-sudo confirmed. The CRITICAL packer DoS is closed (memoised).

## Testing Results
- **Install + upgrade:** ✅ clean. v19-CLEAN.
- **Unit tests:** ✅ **0 failed / 0 error / 18 tests** — the whole suite runs in **0.11s** (pre-fix, the new no-exact-fit test's 4.2m gap alone was ~292M calls / a multi-second hang → the suite would have timed out).
- **New regression tests (all pass):** `test_no_exact_fit_float_gap_terminates_fast` (P1), `test_zero_width_does_not_infinite_recurse`, `test_bad_width_pref_rule_rejected_at_save` (S4 — ValidationError on bad width + bad clearance).

## Recommendations (priority)
1. **S3** — move placement-rule write authority to an engineering/manufacturing group.
2. **LOW-2/P3** — warn on dropped appliances; parse raw JSON once.
3. **S2** — consider content-hashing confirmed AI geometry (workspace module).
