# TEST_RESULTS — southbrook_payroll_ca

**DB:** `ci_pay37` (isolated, full southbrook MI dep stack staged at `/mnt/extra-addons`)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Baseline (HEAD, before fixes)
`-i` + `--test-tags=/southbrook_payroll_ca`: install clean (~63 s), **19 tests, 0 failed / 0 error**.
(An unusually clean baseline — the defects fixed were latent correctness/integrity
bugs not covered by the existing tests, e.g. the paid-run recompute path and the
free-text additional-tax parse.)

## After fixes (19.0.2.0.0)
```
southbrook_payroll_ca: 21 tests
0 failed, 0 error(s) of 13 post-tests when loading database 'ci_pay37'
```

| Phase | Result |
|-------|--------|
| `-i southbrook_payroll_ca` (fresh DB, incl. CRA/WSIB seeds + sequences + cron + mi_tiles seed) | **clean**, registry ~63 s |
| `-u southbrook_payroll_ca` | **clean**, 2.2 s |
| `--test-tags=/southbrook_payroll_ca` (21 tests) | **21 pass / 0 fail / 0 error** |
| mi_tiles probe (`odoo shell`) | `mi_tiles_default` materialized; `headcount=21` — no crash |

## New regression tests
- `test_recompute_blocked_on_paid_run` — a `paid` run raises on `action_compute`
  (PAY-1: previously only `posted` was blocked).
- `test_additional_tax_parses_first_amount_only` — `"$25.00 / period — TD1 Jan 2026"`
  yields `additional_tax == 25.00`, not a digit-concatenation (H4).

## Existing coverage
`test_cra_calc` (federal/Ontario brackets, CPP below/at YMPE, EI, WSIB, EHT),
`test_certification` (expiry status valid/expiring/expired + cron posts activity),
`test_payroll_run` (payslip-per-employee, totals balance, recompute guards,
journal entry), `test_roe` (Box 15C aggregation over 27 periods), `test_t4_preview`
(Box 14 gross, Box 22 taxes).

## Notes
- The `@class`/RST "Unexpected indentation" warnings during `-i` originate from other
  modules' views (kitchen design form, portal sidebar) — pre-existing, unrelated to
  payroll, non-fatal (registry loads, all tests pass).
