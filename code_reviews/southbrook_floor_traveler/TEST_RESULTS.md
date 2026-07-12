# TEST_RESULTS — southbrook_floor_traveler

**DB:** `ci_floor44` (isolated, full dep stack: mrp/sale/kitchen_mrp/premium_orch/mrp_pm)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Baseline (HEAD, before fixes)
`-i` + `--test-tags=/southbrook_floor_traveler`: install clean, **0 fail + 1 error of 6**.
- `test_record_scan_creates_one_consumption_and_logs_workcenter` **ERROR** in setUp —
  `mo.action_confirm()` raised the premium_orchestration MO **availability gate** (no
  component stock staged).

## After fixes (19.0.2.0.0)
```
southbrook_floor_traveler: 7 tests
0 failed, 0 error(s) of 7 tests when loading database 'ci_floor44'
```

| Phase | Result |
|-------|--------|
| `-i` (fresh DB, full dep stack) | **clean**, registry ~70 s |
| `-u` | **clean**, 2.2 s |
| tests | **7 pass / 0 fail / 0 error** |

## What was fixed in the tests
- **Availability-gate bypass** in the setUp helper (`bypass_availability_gate=True`).
- **Asset seed-collision** — once setUp passed, the consumption test failed
  `asset(1) != asset(45)`: the resolver picked the **seeded** melamine-blade asset in the
  shared `cat_blade_melamine` category. Fixed by creating a **fresh** tool category for
  the test so only its own asset matches (same isolation issue documented in module 43).

## New regression test
- `TestP8ScanEndpointAuth.test_non_mrp_user_is_forbidden` (HttpCase) — a `base.group_user`
  user POSTs to `/southbrook/api/floor-traveler/scan` and receives `{"ok": false,
  "error": "forbidden"}` (regression for the IDOR gate).

## v19 confirmation
- v19 agent verified `type="json"` is a **working deprecated alias** in this build
  (`odoo/http.py` auto-converts to `jsonrpc`) — the endpoint was functional; the rename is
  future-proofing. QWeb report + `@api.depends` + all cross-module fields verified valid.
