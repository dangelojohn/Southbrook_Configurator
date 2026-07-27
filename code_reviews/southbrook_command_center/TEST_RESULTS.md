# TEST_RESULTS — southbrook_command_center

**DB:** `ci_cmd46` (isolated, full ~15-module southbrook platform dep chain)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Baseline (HEAD, before fixes)
`-i` + `--test-tags=/southbrook_command_center`: install clean (~80 s), **19/19 pass, 0 error**.

## After fixes (19.0.2.0.0)
```
southbrook_command_center: 21 tests
0 failed, 0 error(s) of 21 tests when loading database 'ci_cmd46'
```

| Phase | Result |
|-------|--------|
| `-i` (fresh DB, full platform dep chain) | **clean**, registry ~80 s; the new `ir.rule` + model ref resolve |
| `-u` | **clean** |
| tests | **21 pass / 0 fail / 0 error** |

## New regression tests (HttpCase — `TestCommandCenterAuth`)
- `test_non_member_is_forbidden` — a `base.group_user`-only user POSTs to
  `/command_center/bootstrap` and gets a jsonrpc **error** envelope (no `result`).
- `test_cc_member_is_allowed` — a `group_command_center_user` member gets a `result`
  containing `factory_health`. (The "panel failed" logs during this test are the designed
  try/except degradation — the test member lacks exec/mrp read, so panels return empty
  while the endpoint still responds; the assertion is on `result`, which holds.)

## v19 / cross-module confirmation
- v19 agent verified **zero foreign `@api.depends`** (registry-safe by AbstractModel design)
  and that **every** cross-module field/method/Selection across the ~15 dep modules exists in
  v19 (mi.check, breakdown_alert, ncr, hermes.recommendation, mi_tiles, exec snapshot,
  sale.order mrp_pm fields, project.task project_mrp fields, find_training).
- Security agent adversarially confirmed **margin/PO-risk are not exposed** (scoring methods
  need a recordset arg, unreachable via call_kw).
