# TEST_RESULTS — southbrook_exec_dashboard

**DB:** `ci_exec42` (isolated, full MI/kitchen/quality/finance/integrations dep stack)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Baseline (HEAD, before fixes)
`-i` + `--test-tags=/southbrook_exec_dashboard`: install clean (~93 s), **3/3 pass, 0 error**.
(A green baseline that masked a CRITICAL — `test_exec_api` authenticated as **admin**,
whose session passed the group-less `_authenticate`, so the no-group-gate financial
leak wasn't exercised; and the OWL/tile bugs are frontend/data, not unit-tested.)

## After fixes (19.0.2.0.0)
```
southbrook_exec_dashboard: 4 tests
0 failed, 0 error(s) of 4 tests when loading database 'ci_exec42'
```

| Phase | Result |
|-------|--------|
| `-i southbrook_exec_dashboard` (fresh DB, full dep stack + OWL assets) | **clean**, registry ~64 s |
| `-u southbrook_exec_dashboard` | **clean**, 2.2 s |
| `--test-tags=/southbrook_exec_dashboard` (4 tests) | **4 pass / 0 fail / 0 error** |

## New / adjusted tests
- `test_exec_api_returns_json` — now grants the exec group to admin first (the
  endpoint is gated); still asserts 200 + all payload keys.
- `test_exec_api_forbids_non_exec_user` (NEW) — a plain internal user (base.group_user
  only) gets **403** from `/exec/morning` (regression C1).

## Field / schema probes
- `southbrook.api.key` has `key_hash` (no cleartext `key` field) — root cause of the
  broken C2 API-key search; now uses `verify()`.
- `southbrook.ncr.state` = draft/quarantine/rework/scrap/released/cancelled (the tile
  used non-existent open/new/in_progress — F2).
- `southbrook.finance.wip_report.total_wip_value` is the real WIP field (F4).

## Notes
- The OWL frontend fixes (F1 blank-render, F3 drill-through) are asset/JS — validated
  by clean asset compilation on `-i`/`-u` (registry + bundle build) and `node --check`;
  full render is a browser concern outside `--test-enable`.
- Pre-existing core-website `@class`/RST warnings during `-i` are unrelated, non-fatal.
