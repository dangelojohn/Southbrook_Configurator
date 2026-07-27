# CHANGELOG — `southbrook_config_engine`

## 19.0.0.2.0 — 2026-07-11 — Code-review pass (Module #20)

### Performance
- **[CRITICAL] `_greedy_pack` is now memoised.** It required an exact ±1mm
  partition and otherwise walked the entire composition tree — a 4.2m gap was
  ~292M recursive calls (multi-second worker hang) on nearly every placement
  (widths are ×25, gaps are arbitrary floats). Memoising on `round(length_mm)`
  (fractional part invariant under integer-width subtraction) collapses it to
  pseudo-polynomial DP, returning the identical first-fit plan.
  `models/southbrook_config_engine.py`.

### Data-integrity / correctness
- **[MEDIUM] `_check_constraint_json` now validates per-kind semantics** —
  width_pref widths must be positive numbers, clearance mm non-negative numbers
  — so a bad rule fails with a clean `ValidationError` at save, not a runtime
  500 / infinite recursion. The packer also filters non-positive widths.
  `models/sb_placement_rule.py`, `models/southbrook_config_engine.py`.
- **[LOW] "blank = all" rule scoping now works** for `appliance_kind` (clearance)
  and `theme` (width_pref) — a blank-scoped rule previously matched nothing,
  contradicting the field help. `models/southbrook_config_engine.py`.

### Tests
- Added `test_no_exact_fit_float_gap_terminates_fast`,
  `test_zero_width_does_not_infinite_recurse`,
  `test_bad_width_pref_rule_rejected_at_save`. **18/18 green**, suite runs 0.11s.

### Notes (documented, not changed)
- Placement-rule write authority is a Sales group, not engineering, though rules
  drive production cuts (S3, governance).
- GAP-02 gate is flag-based, not content-hash-based (S2, workspace-owned).
- No `eval`, no `sudo`, no N+1, complete ACL, GAP-02 enforced — all confirmed.
