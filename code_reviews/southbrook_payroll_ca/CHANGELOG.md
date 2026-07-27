# CHANGELOG — southbrook_payroll_ca

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #37)

### Fixed — correctness / integrity
- **Additional-tax over-withholding (H4).** `models/payslip.py`
  `_compute_additional_tax` now extracts the first numeric token via `re.search`
  instead of concatenating every digit of the free-text field; added
  `contract_id.additional_federal_tax_request` to `@api.depends`.
  (`"$25.00 / period — TD1 Jan 2026"` → `$25.00`, was `$252,026`.)
- **Paid-run recompute (PAY-1).** `models/payroll_run.py` `action_compute` now
  blocks `state in ("posted", "paid")` (was `"posted"` only) — a paid run could
  otherwise be recomputed, unlinking paid payslips and orphaning the journal entry.
- **Double-post idempotency (M7).** `action_post` refuses to run if `run.move_id`
  is already set, so a state laundered back to `computed` can't mint a second move.
- **Stale deduction computes (stale-1).** `_compute_deductions` / `_compute_employer`
  now depend on `contract_id.pay_periods_per_year` / `contract_id.wsib_rate_pct` so
  contract edits repropagate to existing payslips.
- **Bracket constants (L1).** `models/cra_calc.py` + `data/cra_brackets_2026.xml`:
  federal top cumulative `58686.775`→`58686.725`; Ontario `12445.4765`→`12445.5965`
  and `20957.4765`→`20957.5965` (naive-cumulative arithmetic was off; high earners).

### Fixed — cron / compute hygiene
- **Cert cron (M5 + M8).** `models/certification.py` `cron_alert_expiring` now
  (a) recomputes stored `expiry_status` on every dated cert nightly so counts /
  kanban grouping don't go stale, (b) dedups against an existing open renewal
  activity instead of scheduling a fresh to-do every day, and (c) wraps each cert
  in `try/except` so one bad row doesn't abort the sweep.

### Fixed — dead feature
- **Payroll MI tiles (mi_tiles).** `security/ir.model.access.csv` grants manager
  create/unlink on `southbrook.payroll.mi_tiles`; new `data/mi_tiles.xml` seeds one
  `noupdate` `Payroll Snapshot` record so the MI dashboard has a row to read.

### Tests
- `tests/test_payroll_run.py` +2 regression tests: `test_recompute_blocked_on_paid_run`,
  `test_additional_tax_parses_first_amount_only`.

### Not changed (documented in REVIEW_REPORT.md — tax-law / v1-scope / policy)
- H1 YTD tracking for CPP/EI caps (the key follow-up); H2/H3 T4/ROE issued-lock
  (models are explicitly previews, filing out of v1 scope); M1 employer CPP/EI match;
  M2 TD1 amount threading; M3 Ontario surtax + OHP; M4 CPP2 tier; M6 T4 box 24/26
  MIE/YMPE caps; L2 JE-left-in-draft + employer costs unbooked; L3 EHT projection
  labeling; L4 ROE ordering/hours; clerk contract-write policy.

### Manifest
- `data/mi_tiles.xml` added; version `19.0.1.0.0` → `19.0.2.0.0`.
