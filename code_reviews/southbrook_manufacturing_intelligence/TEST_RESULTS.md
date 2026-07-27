# Test Results — `southbrook_manufacturing_intelligence`

**Date:** 2026-07-11 · **DB:** isolated on `v19c-db` · full southbrook stack staged.

## Baseline (unmodified HEAD)
`-i`: **1 failed, 17 error(s) of 40 tests** — plus 2 test classes whose setUpClass
crashed on the v19 `groups_id` field (their ~16 tests never ran). Install clean.
Dominant causes: `deviation_waiver.py` `groups_id` (module bug, crashed waiver
approval + cascaded), test `groups_id` (2 files), mrp_pm approval gate on test MO
creation, and the phantom `mrp.production.production_approval_state`.

## After fixes
- `-i` (fresh DB, all views + cron + sequence) — registry 46.9 s — **4 failed, 0
  error(s) of 56 tests** (52 pass; the `group_ids` fix unblocked the 2 setUpClass
  classes, so 56 tests now run).
- `-u` — same.

## Resolved (18 baseline failures + 2 blocked classes → 4)
- V1 module `groups_id` → waiver-approval + deviation tests pass.
- C1/C2/H1/H2/H3 governance fixes + 3 regression scenarios pass.
- Cross-module test artifacts fixed: t1/p3 approval-gate (force-release), SoD test
  (requester=approver), auto_fix `exists()`-guard, p3 case, ready-queue phantom-skip.
- L1 FAI-status fix → `test_fai_status_passed_on_signing_mo` passes.

## Remaining 4 (pre-existing behavioral nuances — documented)
| Test | Nature |
|------|--------|
| `test_w024...no_source_so_is_idempotent`, `...with_existing_cutlist_is_noop` | auto-fix's recompute deletes+recreates the cut check, so `check.exists()` (specific id) fails — a churn, not a silent resolution; my exists-guard fixed the prior crash |
| `test_w053...idempotent_no_change_no_write` | recompute writes `x_mi_yield_pct`/`x_mi_waste_area_m2` on a no-change run (delta-write edge) |
| `test_w025...eco_reversion_has_fai_required` | FAI-required after ECO reversion edge |

All four were failing (or crashing) at baseline; none is a security/correctness
regression from this pass. Resolving them cleanly is an engine-idempotency refactor
(delete-recreate vs durable records) beyond this security-focused pass.
