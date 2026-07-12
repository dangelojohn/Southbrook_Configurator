# Test Results — `southbrook_plm` (Module #15)

**Harness:** OrbStack `v19c-odoo`, isolated throwaway DB, staged `southbrook_plm`
+ dep chain (`southbrook_estimating`, `southbrook_qr_kit`) over the 4 OCA modules.
Never run against prod/QNAP.

## Install / upgrade
- **Fresh install** (`-i southbrook_plm`): ✅ SUCCESS — the rewritten `write()`
  guard, approver gates, `_apply_bom` row-lock, and batched snapshot all load.
- **Upgrade** (`-u`): ✅ SUCCESS.

## Unit tests
`--test-enable --test-tags southbrook_plm` → ✅ **0 failed, 0 error(s) of 21 tests**
(both install and upgrade runs).

### New regression tests (all pass)
- `test_direct_write_cannot_forge_terminal_state` — a plain PLM User's
  `write({"state":"applied"})` and `write({"stage_id":applied,"state":"applied"})`
  both raise `UserError`, and `state`/`approver_id` stay unset. **This is the
  exact hole the old guard let through** — it passes only with the H1 fix.
- `test_plain_user_cannot_reject` — plain user `action_reject()` raises.
- `test_plain_user_cannot_reset_applied_eco` — plain user `action_reset_draft()`
  on an applied ECO raises; the approver can still reset (→ `state=open`).

### Pre-existing tests still green
`test_bom_eco_versions_and_archives` (now exercises the `_apply_bom` FOR UPDATE
lock + archived-check — still versions v1→v2 and archives the original),
`test_cut_spec_eco_apply_changes_seam`, `test_plain_user_cannot_apply`,
`test_approval_required_stage_gating`, the panel-math + rule-ECO tests, and the
cut-spec-version suite — the `action_apply`/`action_reject` `plm_lifecycle` flag
lets their legitimate terminal writes through the new guard.

## Static / cross-checks
- `python3 -m py_compile` on all changed models + tests: ✅
- v19-compat audit: **CLEAN** — no v19 breakages (v19-aware groups, correct
  `mrp.bom.copy()` versioning, all cross-module xpaths resolve).
- Security audit: **no CRITICAL** — no controllers/eval/SQL/`sanitize=False`; all
  `sudo()` calls verified (the one privileged BoM mutation stays behind the
  approver-gated Apply).

## Conclusion
The best-governed module reviewed so far — proper group-scoped ACL and
approver-gated actions — but its workflow-bypass guard had a forge hole, two
ungated lifecycle actions, and an apply-time TOCTOU. All are closed and guarded
by regression tests; the privileged BoM mutation was never reachable by a
non-approver. Install + upgrade clean, full suite green. Tolerance bounds (D1),
activation-race lock (D3), and stage-seed `noupdate` (D2) are documented owner
decisions.
