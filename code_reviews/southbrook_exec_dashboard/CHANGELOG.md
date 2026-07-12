# CHANGELOG — southbrook_exec_dashboard

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #42)

### Fixed — security
- **Executive-group gate on the controller (C1, CRITICAL).**
  `controllers/exec_api.py` — `/exec/morning` now requires the caller be an
  internal user in `group_southbrook_exec_dashboard_user` (403 otherwise),
  checked BEFORE the sudo KPI compute. Previously any logged-in session
  (incl. portal customers) read company revenue/cash.
- **API-key path uses verify() (C2, CRITICAL).** `_authenticate` calls
  `southbrook.api.key.verify()` (timing-safe hash) instead of the broken
  `search([("key","=",api_key)])` (no such field; bypassed the hash).
- **NCR counts company-scoped (H1, HIGH).** `models/exec_snapshot.py` — both
  NCR `search_count`s now filter `company_id` (field-guarded); fixes a
  cross-company leak and a corrupted FPY numerator.

### Fixed — frontend / KPI correctness
- **Dashboard no longer blank (F1, HIGH).** `static/src/js/morning_briefing.js`
  — `useService("user")` (removed in v19) replaced with
  `import { user } from "@web/core/user"`.
- **Critical-NCR tile + drill-through (F2/F3).** NCR `state` filter uses the real
  values `draft/quarantine/rework` (the old `open/new/in_progress` matched
  nothing → tile always 0); OWL drill-through domain fixed + `severity="critical"`.
- **WIP tile (F4).** `models/exec_snapshot.py` — added `total_wip_value` (the real
  field on `wip_report`) to the field-name lookup; WIP was always $0.
- **Unbounded snapshot growth (M3).** The OWL client routes through
  `get_or_create_today` (5-min dedup) instead of `create({})` per open;
  `get_or_create_today` now returns an int id (RPC-serialisable) and the
  controller browses it.
- **Cash dedup (L3).** Bank/cash journals sharing one `default_account_id` no
  longer double-count.

### Tests
- `tests/test_exec_api.py` — grant the exec group to admin (endpoint is now
  gated); +1 regression test `test_exec_api_forbids_non_exec_user` (non-exec
  internal user → 403).

### Not changed (documented in REVIEW_REPORT.md)
- M1 tz day-boundary mixing; M2 payload caching / rate-limit; M4 revenue excludes
  credit notes; L1 takt population mismatch; L2 empty-day "perfect" defaults;
  F5 missing web_icon; F6 bottleneck soft-deps mes_mps; F7 dead snapshot action;
  F8 viewer create perm (needed by get_or_create_today).

### Manifest
- Version `19.0.1.0.0` → `19.0.2.0.0`.
