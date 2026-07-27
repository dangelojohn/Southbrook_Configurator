# Code Review — `southbrook_manufacturing_intelligence`

**Module #35 of 46 · Odoo 19.0 CE**
**Version:** 19.0.3.6.4 → **19.0.4.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+governance; v19+correctness) →
independent source verification → HEAD baseline → real fixes + test repairs → live
`-i`+`-u`+tests on isolated DB (`ci_mi`, full southbrook dep stack staged).

## What the module does
Manufacturing Intelligence: `southbrook.mi.check` quality checks (cut/cad/install/
assembly/hardware/fai), a check **engine** (auto-fix / auto-remediate), a
**deviation-waiver** governance flow (lets an out-of-spec cabinet ship after
engineering sign-off), a **FAI** (first-article-inspection) gate, and a 5-min
recompute cron.

## Verdict
The module is **v19-clean** (v19 agent: installs/upgrades/mounts cleanly, all
`@api.depends` resolve, all cross-module fields traced). But the **action-layer
governance was not backed at the data layer**, and the engine's delete-all-recreate
recompute destroyed the very quality records the governance depends on. Fixed the
**2 CRITICAL + 3 HIGH** governance defects + the 1 real v19 bug. Baseline **18
failures → 4** (the 4 remaining are pre-existing behavioral nuances, documented).

## Findings

### Fixed — v19 correctness
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| V1 | HIGH | `deviation_waiver.action_approve` used `self.env.user.groups_id` (removed in v19) → **waiver approval crashed** with `AttributeError`. | `group_ids`. |

### Fixed — security / governance
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **C1** | **CRITICAL** | **Waiver approval bypassable by raw `write()`.** QC has ORM write on `southbrook.deviation.waiver`; every gate (eng-group, SoD, customer-ack, terminal-state) lived only in `action_approve`. A `write({"state":"approved"})` skips all of it → out-of-spec cabinet ships with a forged approver, zero sign-off. | `write()` guard blocking the `approved` transition unless via `action_approve` (which sets a private context flag). |
| **C2** | **CRITICAL** | **`mi.check.state` raw-writable to `ship_with_deviation`.** A QC could `write({"state":"ship_with_deviation"})` — laundering a failing check straight to ship, with **no waiver at all** (no eng sign-off, no customer ack); warranty-trace then shows a legitimate-looking deviation. | `write()` guard: `ship_with_deviation` only via the waiver approval's sudo path. |
| **H1** | **HIGH** | **The 5-min cron destroyed FAI checks + manual NCRs.** `_unlink_existing_checks` deleted **every** check on the MO then recreated only engine ones — so the pending FAI check (the inspector's sign-off surface) and any manual NCR vanished within one sweep, permanently gating the MO with no surface / silently losing quality records. | Scoped the unlink to engine categories (`cut/cad/install/assembly/hardware`), sparing `fai` + manual `production` NCRs. |
| **H2** | **HIGH** | **Recompute FK-crashed for any MO with a waivered check.** `deviation_waiver.mi_check_id` is `ondelete="restrict"`; the delete-all hit the FK (sudo doesn't bypass a DB constraint) → the cron swallowed it and the MO's MI status froze stale forever. | Same scoping also excludes `deviation_waiver_id`-set checks. |
| **H3** | **HIGH** | **SoD void for engine-created NCRs.** `action_approve` compared the approver to `mi_check_id.create_uid`, but engine NCRs are `sudo`-created (create_uid = OdooBot) → SoD never tripped for auto-generated blockers (the majority): the same manager could raise a waiver and approve it. | Compare against the **waiver requester** (`rec.create_uid`). |
| **L1** | LOW | Passed FAI showed `fai_status='not_required'` instead of `passed` (`action_fai_pass` retires the check to `active=False`; the One2many read applied `active_test` and dropped it). | `_compute_fai_check_id` reads with `active_test=False`. |

### Fixed — tests
group_ids in 2 test files (v19), t1/p3 `force_production_release` past the mrp_pm gate,
SoD test now makes the requester the approver (H3), `action_auto_fix` `exists()`-guard
(recompute can delete a sibling/self mid-loop → `MissingError`), p3 chatter-assert
case-fix, `test_ready_queue_split` skips when the phantom `production_approval_state`
field is absent.

### Documented (business-policy / pre-existing — not changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| M1 | MED | FAI `action_fai_pass` has no role gate beyond SoD (any `mrp_user`); a fabricated `fai` check can `sudo`-clear `bom.fai_required`. | Add a "may sign off FAI" group. |
| M2 | MED | Auto-remediation (`_AUTO_REMEDIATE_DEFAULT="True"`) creates production-package/cutlist records unattended as root on the 5-min timer. | Add a human-review gate / surface it. |
| M3 | MED | `mrp.workcenter` KPI compute is an unbounded per-workcenter `search` (N+1 on the dashboard). | `read_group`. |
| — | — | **Cross-module gap:** `mrp.production.production_approval_state` is *read* by `southbrook_mrp_pm._compute_next_action_hint` (getattr) but *defined* nowhere → the approval-pending hint never fires; `test_ready_queue_split` skips. | Add it as a related field in `southbrook_mrp_pm`. |
| — | — | **4 pre-existing test failures** (were failing/crashing at baseline): `test_w024` ×2 (a failed/redundant auto-fix's recompute deletes+recreates the cut check, so the specific `check.id` doesn't survive — a churn, not a resolution; the tests over-assert record identity), `test_w053` (recompute writes `x_mi_yield_pct`/`x_mi_waste_area_m2` on a no-change run — a delta-write idempotency edge), `test_w025_eco_reversion`. | Engine idempotency semantics (delete-recreate vs durable records) — a deeper refactor; the CRITICAL destruction/crash (H1/H2) is fixed. |

## Strong positives (verified)
- Action-layer governance is well-composed (group + requester≠author SoD +
  customer-ack + terminal-state block); FAI SoD even soft-checks the ProductGraph
  release approver. Cron runs as root with per-row `try/except`. No SQL/eval/t-raw.
- **v19-clean**: correct `@api.model_create_multi`, `group_ids`, `ir.cron`/`ir.sequence`
  schema, no `<function obj()>`, all cross-module fields (`sale_line_id`, freecad
  `x_cad_status`, `lot_producing_ids`, package/cutlist/hardware) traced to source.

## Validation
- `-i` (fresh DB, incl. all views + cron + sequence) — **clean install**, registry
  ~47 s.
- `-u` — clean.
- Tests `--test-tags=/southbrook_manufacturing_intelligence` — **52/56 pass** (4
  pre-existing behavioral failures documented above), from an effective baseline of
  ~18 failures + 2 setUpClass-blocked classes. See `TEST_RESULTS.md`.
