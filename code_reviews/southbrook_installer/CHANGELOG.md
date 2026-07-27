# Changelog — `southbrook_installer`

## 19.0.4.0.0 — 2026-07-10 (code review #4)

A well-built module with two serious latent issues fixed (a dead v19 bus API
and a missing record-rule security model), plus perf. Baseline suite was green
(25); now 28 green.

### Fixed
- **v19 CRITICAL — dispatcher live bus dead:** `bus.bus._sendmany()` was
  removed in v19; every damage-flag create/resolve hit it and raised
  `AttributeError` (swallowed by a broad except), so the OWL board silently
  fell back to polling. Now `bus.bus._sendone(...)`.
- **Perf HIGH:** `index=True` on `stage_is_terminal` (the default filter on
  every Jobs screen + the dashboard default).
- **Perf MED:** `store=True` on the 4 dashboard-polled counters
  (`tool_loan_count`, `tool_loan_open_count`, `stage_log_count`,
  `stage_log_done_count`).
- **Perf MED:** `_spawn_phase_logs` batched across the create-batch (phases
  queried once; one `Log.create`).
- **LOW:** trimmed a dead `stage_id.sequence` `@api.depends` on `_compute_color`.
- **Docs:** corrected the unachievable "2-hour deadline" claim on the
  dispatcher activity (`mail.activity.date_deadline` is a `Date`).

### Added — SECURITY (behavior change)
- **`security/southbrook_installer_record_rules.xml`** — 14 `ir.rule` records
  enforcing the documented per-installer model: crew (helper/lead) see only
  jobs they lead or are crewed on; dispatcher/warehouse/finance/ops keep
  company-wide visibility. Closes cross-crew exposure of customer
  addresses/GPS/photos/builder signatures. **Requires crew assignments to be
  populated; confirm the intended visibility model before deploy.**

### Added — tests
- `tests/test_southbrook_installer_security.py` — bus-notify regression,
  crew-sees-only-assigned, dispatcher-sees-all.

### Reverted mid-review
- A `groups_id` on the dispatch-board `ir.actions.client` — invalid in v19
  (`ir.actions.client` has no `groups_id`; broke install). Gating is by menu
  `groups=` + the record rules (which scope the dashboard's `searchRead`).

### Known / deferred (documented)
`action_confirm_all_ok` per-line writes (bounded 250), missing app icon,
warehouse ACL on closeout lines, multi-company `company_id`. See `REVIEW_REPORT.md`.

### Verified clean (no change)
All 13 v19 axes, ACL completeness (14 models), state-machine gates, no
SQL/sudo/eval, dashboard services. The module already avoids the codebase's
recurring traps.
