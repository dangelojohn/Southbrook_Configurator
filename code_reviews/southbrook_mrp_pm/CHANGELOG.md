# Changelog — `southbrook_mrp_pm`

## 19.0.1.13.0 — 2026-07-11 (code-review pass, module #27)

### Security — Fixed
- **F1 (HIGH) — approval-gate state-laundering.** Added a value-aware `write()`
  override on `sale.order`: a non-approver may not set `production_approval_state`
  to `"approved"`, and a non-manager may not set `force_production_release`
  (superuser/sudo exempt). Views gate the buttons; this gates `call_kw`/XML-RPC —
  the MO-create gate trusts exactly these two fields.
- **F1b (HIGH)** — `action_approve_production` now checks the
  `group_southbrook_production_approver` group in the method body (not just the
  view button), since releasing production is RPC-reachable.
- **F2 (HIGH) — Order Builder `send_to_production` sudo path.** The
  `send_to_production` branch (`controllers/order_builder.py`) now rejects
  `request.env.user.share` (portal dealers/customers may not create MOs under
  sudo), checks `production_approval_state` (defense-in-depth), and catches
  `AccessError` → `forbidden` (previously only `UserError` was caught → 500).
  Mirrors the parent's `send_to_manufacturing` guard.

### Audit trail
- The manager `force_production_release` bypass is now logged to the source SO's
  chatter at the MO-create gate (`mrp_production.py`), once per order. Previously
  the only bypass audit lived in the now-dead `_check_production_approval_gate`.

### Operational safety — Fixed
- **F4 (MEDIUM)** — the activity-retention cron (`mail_activity.py`) now deletes in
  bounded batches (1000/chunk), committing between batches to cap memory +
  transaction/lock size (the table can reach 10M+ rows). Commit is skipped under
  `--test-enable` (v19 `TestCursor` forbids commit).

### Tests
- Rewrote `test_so_blocked_without_approval` + `test_so_bypass_with_manager_flag`
  to validate the actual MO-create gate (the gate-at-confirm design was
  intentionally abandoned) + the new bypass audit.
- Fixed test bugs: `test_w051` set→list (unhashable `in`-leaf), `test_w056`
  `.original_routing` (v19 route-metadata attr), `test_w057` `flush_recordset()`
  (stored-computed `date_done`), `test_w019` `skipTest` when MI is absent.
- Added `test_state_laundering_blocked_for_non_approver`,
  `test_force_release_self_grant_blocked_for_non_manager`,
  `test_approve_action_requires_approver_group`.

### Not changed (documented in REVIEW_REPORT.md)
- F3 floor per-station authorization (needs an operator→workcenter mapping —
  access-model decision), F5 kiosk/shop-daily N+1 (read_group refactor), F6 dead
  `_check_production_approval_gate` (harmless), and the dependency's
  `test_send_to_manufacturing` cross-module precedence artifacts.
