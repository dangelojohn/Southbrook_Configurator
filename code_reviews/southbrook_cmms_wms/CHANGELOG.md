# CHANGELOG — southbrook_cmms_wms

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #40)

### Fixed — crash / correctness
- **Expiry cron crash (V1, HIGH).** `models/service_contract.py` —
  `manager_group.users` → `manager_group.all_user_ids` (v19 removed
  `res.groups.users`). The cron failed 100% of runs.
- **Stale expiry state (C1, CRITICAL).** The daily cron now `invalidate`s +
  force-recomputes `days_to_expiry`/`state` (stored computes keyed on `date_end`,
  not "today") before filtering — they no longer freeze as the calendar advances.

### Fixed — cron hygiene
- **Expiry re-alert throttle + isolation (M6).** New `last_alert_date` field;
  the cron re-alerts at most weekly and wraps each contract in `try/except`.
- **MTBF cron dedup (M7).** `models/mtbf_mttr_report.py`
  `_cron_generate_daily_reports` upserts one report per `(equipment, as_of_date)`
  instead of creating a fresh row every run.
- **Back-dated downtime clamp (M9).** Each outage is clamped to
  `[period_start, as_of_date]` so a still-open request on a past-dated report
  can't count downtime beyond the window.

### Fixed — honesty / dead feature
- **False "Blocked N MOs" (H3-copy).** `models/breakdown_alert.py` — the MO
  message + notification now say "**Flagged** N MO(s) … do not run production
  until cleared" (the action only flags; it does not hard-block).
- **mi_tiles seed (M8).** New `data/mi_tiles.xml` seeds one `noupdate`
  `Maintenance & Logistics Snapshot` record (menu was empty; users can't create).

### Tests
- `tests/test_cmms_wms.py` — dropped the removed `stock.move.name` key from the
  move command dicts (fixes the baseline `KeyError` error); +1 regression test
  `test_expiry_cron_runs_and_deduplicates` (no crash, alert posted,
  `last_alert_date` stamped, same-week re-run throttled).

### Not changed (documented in REVIEW_REPORT.md — policy / cross-module / statistical)
- H2+F2 oversize-permit gate inert (no dimension provider) + unenforced (no
  button_validate override); H3 breakdown hard-block enforcement model; H4
  zero-failure MTBF presentation; H5 MTTR 24h resolution; L11 landed-cost account/
  product_id; L12 breakdown MO mapping; F3 landed-cost company filter; F4 unused deps.

### Manifest
- `data/mi_tiles.xml` added; version `19.0.1.0.0` → `19.0.2.0.0`.
