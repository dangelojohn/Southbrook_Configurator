# Changelog — `southbrook_manufacturing_intelligence`

## 19.0.4.0.0 — 2026-07-11 (code-review pass, module #35)

### v19 correctness — Fixed
- **V1** — `deviation_waiver.action_approve` uses `self.env.user.group_ids` (was the
  v19-removed `groups_id`, which crashed waiver approval with AttributeError).

### Security / governance — Fixed
- **C1 (CRITICAL)** — `southbrook.deviation.waiver.write()` blocks the `approved`
  transition unless via `action_approve` (which sets `_sbk_waiver_approve_action`
  and enforces eng-group + SoD + customer-ack). A raw `write({"state":"approved"})`
  previously bypassed the entire governance.
- **C2 (CRITICAL)** — `southbrook.mi.check.write()` blocks `state="ship_with_deviation"`
  unless via the (sudo) waiver-approval path. Previously a QC could launder a
  failing check straight to ship with no waiver.
- **H1/H2 (HIGH)** — `mi_engine._unlink_existing_checks` now scopes to engine
  categories (`cut/cad/install/assembly/hardware`) AND `deviation_waiver_id = False`
  — it no longer deletes FAI checks / manual `production` NCRs (H1) and no longer
  FK-crashes the whole recompute on a waivered check (H2, `mi_check_id` is
  `ondelete=restrict`).
- **H3 (HIGH)** — waiver SoD compares the approver to the **waiver requester**
  (`rec.create_uid`), not the NCR author (which is OdooBot for engine checks, so SoD
  never tripped).
- **L1** — `mrp.production._compute_fai_check_id` reads `x_mi_check_ids` with
  `active_test=False` so a passed (retired) FAI check surfaces `fai_status='passed'`.

### Tests
- `group_ids` (v19) in test_w025/test_deviation; `force_production_release` in
  t1/p3 (mrp_pm gate); SoD test makes the requester the approver; `action_auto_fix`
  `exists()`-guard (recompute deletes checks mid-loop → MissingError); p3 chatter
  case-fix; test_ready_queue_split skips when `production_approval_state` is absent.

### Not changed (documented in REVIEW_REPORT.md)
- M1 FAI role gate, M2 unattended auto-remediation, M3 workcenter KPI N+1, the
  `mrp.production.production_approval_state` cross-module phantom-field gap, and 4
  pre-existing behavioral test failures (auto-fix recompute churn ×2, cron
  yield/waste delta-write idempotency, FAI-eco-reversion).
