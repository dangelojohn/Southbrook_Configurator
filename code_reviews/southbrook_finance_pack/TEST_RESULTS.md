# TEST_RESULTS — southbrook_finance_pack

**DB:** `ci_fin36` (isolated, full southbrook MI dep stack staged at `/mnt/extra-addons`)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Baseline (HEAD, before fixes)
`-i` + `--test-tags=/southbrook_finance_pack`: install clean, **1 failed + 2 error of 15**.
- `test_budget` ×2 **ERROR** — `KeyError: 'company_id'` in `setUp` (searched/created
  `account.account` with the v19-removed `company_id`).
- `test_cca_schedule.test_class_29_straight_line` **FAIL** — $9999.99 vs $10000
  (per-year rounding left a $0.01 residual).

## After fixes (19.0.2.0.0)
```
southbrook_finance_pack: 15 tests 0.18s 543 queries
0 failed, 0 error(s) of 15 tests when loading database 'ci_fin36'
```

| Phase | Result |
|-------|--------|
| `-i southbrook_finance_pack` (fresh DB, incl. CCA seed + sequences + `post_init_hook` + `mi_tiles` seed) | **clean**, registry ~66 s |
| `-u southbrook_finance_pack` | **clean**, 2.1 s |
| `--test-tags=/southbrook_finance_pack` (15 tests) | **15 pass / 0 fail / 0 error** |
| F3 tile-render probe (`odoo shell`) | `mi_tiles_default` materialized; tiles compute live (`cash=4190.93, wip=0.0, hst=0.0, rev30=76324.0`) — no crash |

## Tests covered
`test_budget` (variance formula, zero-budget guard), `test_cca_schedule` (Class-8
declining balance, Class-29 straight-line, AII first year, regen-if-posted guard,
schedule persistence + corrected NBV progression), `test_hst` (creation/state,
net-owing formula, Q3/Q4 period windows, per-year/quarter uniqueness), `test_wip`
(compute reset, total sums, line valuation).

## Notes
- A core-website warning traceback (`ir.ui.view.arch` computed-field warning during
  theme specific-view creation) appears during `-i`; it is pre-existing core noise,
  non-fatal (registry loaded, all tests pass), and unrelated to this module.
