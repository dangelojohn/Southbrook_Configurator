# Test Results — `southbrook_kitchen_workspace` (Module #13)

**Harness:** OrbStack `v19c-odoo`, isolated throwaway DB, staged
`southbrook_kitchen_workspace` + dep chain (`southbrook_estimating`,
`southbrook_qr_kit`) over the 4 OCA modules. Never run against prod/QNAP.

## Install / upgrade
- **Fresh install** (`-i southbrook_kitchen_workspace`): ✅ SUCCESS. All changes
  load — the approval `write()` guard, readonly view fields, tightened ACL
  (manager-only unlink on audit models), fixed mail-template CTAs, indexes.
- **Upgrade** (`-u`): ✅ SUCCESS.

## Unit tests
`--test-enable --test-tags kitchen_workspace` → ✅ **0 failed, 0 error(s) of 23 tests**
(both install and upgrade runs).

- Added `test_approval_state_not_writable_directly` — asserts a direct
  `write({'state':'approved'})` on a rejected approval raises `UserError` and the
  state stays `rejected`, while a non-state write (`notes`) still succeeds.
- All pre-existing tests remained green: the state-machine tests drive transitions
  through `action_approve`/`action_reject` (which set the transition context flag),
  so the new guard does not affect them; the lifecycle-email tests still queue mail
  (the CTA fix and sudo change don't alter send behaviour); the one-of-N selection
  test confirms the de-looped `write` preserves the invariant.

## Static / cross-checks
- `python3 -m py_compile` on all changed models + tests: ✅
- XML well-formedness on all changed views + mail templates: ✅
- Verified no code writes `sb.kitchen.approval.state` outside the two guarded
  actions (grep) → the `write()` guard blocks no legitimate caller.
- v19-compat audit: module confirmed **CLEAN** (no v19 breakages).
- Security audit: **no CRITICAL** — no controllers, no external API, no
  eval/SQL/`sanitize=False`; all findings internal-user-gated.

## Conclusion
Small, v19-clean, low-defect module. The integrity/audit holes (approval
state-laundering, confirmation-stamp bypass, audit-record deletion) are closed and
guarded by a regression test; the broken operator-email CTA is fixed. Install +
upgrade clean, full suite green. The who-may-approve policy (D1) and per-designer
isolation (D2) are documented owner decisions.
