# Code Review — `southbrook_payroll_ca`

**Module #37 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.0.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+payroll-math; v19+data/install) →
independent source verification incl. hand-traced payslip + bracket arithmetic →
HEAD baseline → real fixes + regression tests → live `-i`+`-u`+tests + tile-render
probe on isolated DB (`ci_pay37`, full southbrook MI dep stack staged).

## What the module does
A hand-rolled bi-weekly **Canadian payroll engine** for Odoo 19 CE (no Enterprise
`hr_payroll`): CRA 2026 federal + Ontario tax brackets, CPP/EI/WSIB/EHT, payroll
runs → one payslip per employee → a single balanced journal entry, T4-slip preview,
ROE (Record of Employment), and employee **certification** tracking with a daily
expiry-alert cron. Defines its own `southbrook.payroll.contract` (CE 19 ships no
`hr.contract`).

## Verdict
**Unusually clean on both the v19 and security axes:** installs/upgrades cleanly,
registry-safe (every `@api.depends` traced), **no sudo / SQL / eval**, and — verified
— **no PII leak** (`group_southbrook_payroll_user` is *not* implied by
`base.group_user`, so ordinary employees get zero access to payslips/salary; there is
no employee self-service surface). The core tax math is **correct for the uniform
salaried earner** (hand-traced $60k bi-weekly: CPP/EI/federal/Ontario/BPA-as-credit
all per T4127). Defects were concentrated in **state-integrity, a free-text-parse
withholding bug, cron hygiene, and stale computes**; the larger set of items is
**payroll-tax-completeness** that is v1-scoped / needs an accountant. Fixed **8
self-contained bugs**; baseline **19/19 green → 21/21 green** (+2 regression tests).

## Findings

### Fixed — correctness / integrity
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **H4** | **HIGH** | **Free-text additional-tax parsed by digit-concatenation → arbitrary over-withholding.** `contract.additional_federal_tax_request` is a `Char` whose help text tells users to store `"$25.00 / period — TD1 Jan 2026"`; `_compute_additional_tax` kept *every* digit → `"…25…2026"` became **$252,026** of additional withholding (wildly negative net). | Extract the **first numeric token** (`re.search(r"-?\d+(?:\.\d+)?")`); `"$25.00 … 2026"` → `$25.00`. |
| **PAY-1** | **HIGH** | **A PAID run could be recomputed.** `action_compute` blocked only `state == "posted"` — a `paid` run passed the guard, so recompute `unlink()`ed the already-paid payslips and reverted state to `computed`, **orphaning the posted journal entry**. | Guard `state in ("posted", "paid")`. |
| **M7** | **MED** | **Double-post mints a second orphaned journal entry.** No `write()` guard on `run.state`; a manager could raw-write `paid`/`posted` back to `computed` and hit Post again — `move_id` overwritten, first `account.move` orphaned. | `action_post` now refuses if `run.move_id` is already set (idempotency independent of the state field). |
| **stale-1** | MED | **Deduction computes didn't repropagate on contract edits.** `_compute_deductions`/`_compute_employer` depended on `contract_id` (the M2O) but not its sub-fields, so changing `pay_periods_per_year` or `wsib_rate_pct` left existing payslips stale. | Added `contract_id.pay_periods_per_year` / `contract_id.wsib_rate_pct` to the depends (and `contract_id.additional_federal_tax_request` for H4). |
| **M8** | MED | **Stored `expiry_status` went stale.** `@api.depends("expires_at")` + `store=True` → a cert that *crossed* its expiry kept `valid` until some write touched it, drifting the employee's expiring/expired counts (and the kanban grouping, which needs the field stored). | The daily cron now recomputes `expiry_status` on every dated cert (keeps it stored for the kanban, fresh nightly). |
| **M5** | MED | **Cert cron spammed duplicate to-dos + aborted on one bad row.** It scheduled a fresh `activity_schedule` for every in-window cert **every daily run** (~30 dupes/cert) with no per-row `try/except`. | Dedup against an existing open renewal activity; wrap each cert in `try/except` so one failure doesn't poison the sweep. |
| **L1** | LOW | **Upper-bracket cumulative constants arithmetically wrong** (within the module's own ±$2 tolerance so tests passed): federal top `58 686.775`→`58 686.725`; Ontario `12 445.4765`→`12 445.5965` and `20 957.4765`→`20 957.5965` (`44225×0.1116 = 4935.51`). Affects incomes >$150k/$253k only. | Corrected the Python constants **and** the seed XML. |
| **mi_tiles** | LOW | **Payroll MI tiles never surfaced** — `southbrook.payroll.mi_tiles` had `perm_create=0` for both groups and no seed, so the MI dashboard that reads it found no row (same class as finance_pack F3, lower impact — no crashing menu). | Granted manager create/unlink + seeded one `noupdate` `Payroll Snapshot` record. |

### Documented (payroll-tax completeness / v1-scope / policy — needs accountant sign-off, NOT unilaterally changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| H1 | HIGH | **No YTD tracking — CPP/EI use an "as-if-uniform" per-period cap.** Materially under/over-deducts for mid-year hires, bonus periods, or variable hours (e.g. a mid-year hire hitting YMPE over 13 periods under-deducts ~$2,074 CPP). The code comment itself says payslip should track YTD; it doesn't. | The correct fix stores YTD pensionable/insurable per employee-year and clamps the final period — a design change beyond a review edit. **The single most important follow-up.** |
| H2/H3 | HIGH→scope | **T4 preview & ROE are mutable, not locked snapshots.** Both recompute/overwrite freely with no issued/filed state. | Both models are explicitly scoped as *previews* ("informational, not CRA-filing-ready", "filing out of scope for v1"). Add an issued-lock **when filing is implemented** — no "filed" state exists to protect yet. |
| M1 | MED | **Employer CPP match + 1.4× EI never computed** → remittance & payroll JE understate employer statutory cost. | Compute employer CPP/EI, add remittance-payable lines. |
| M2 | MED | **TD1 personal-amount fields are dead** — `cra_td1_personal_amount_*` are collected but the calc uses the hardcoded BPA constants → employees with extra credits are over-withheld. | Thread the contract TD1 amounts into `federal_tax_2026`/`ontario_tax_2026`. |
| M3 | MED | **Ontario surtax + Ontario Health Premium omitted** → provincial under-withholding (~$600/yr OHP at $60k). | T4127 provincial withholding tax-law. |
| M4 | MED | **CPP2 (second additional CPP, YMPE→YAMPE @ 4%) missing for 2026** → earners >$73,200 under-withheld up to ~$396/yr. | Add the CPP2 tier. |
| M6 | MED | **T4 boxes 24/26 use raw gross, uncapped** — EI-insurable must cap at MIE ($66,600), CPP-pensionable at YMPE ($73,200). | Cap in `action_generate_for_year`. |
| L2/L3/L4 | LOW | `action_post` leaves the `account.move` in **draft** (never `action_post()`ed) + WSIB/EHT unbooked; `total_eht` shows full annual per run (26× if summed); ROE Block 15C orders by `create_date` not `pay_date` and uses raw (uncapped) gross for hours/earnings. | v1 accounting/reporting gaps. |
| policy | — | Payroll **clerk** (`group_southbrook_payroll_user`) has write+create on `contract`/`certification` (can set anyone's wage). | Restrict comp-data write to the manager group if clerks should be read-only. |

## Strong positives (verified)
- **No PII leak, no sudo, no SQL, no eval, no record-rule gaps** (there's no self-service surface to need one). ACLs reference only the two payroll groups; the user group implies `hr.group_hr_user` one-way (an HR officer does *not* inherit payroll access).
- Balanced JE (`Dr gross = Cr net + Cr deductions`, and `net = gross − deductions`).
- Correct v1 T4127 method (annualize → bracket → ÷periods; BPA as a non-refundable credit, not an income deduction); CPP basic-exemption prorated; EI per-period MIE cap.
- **v19-clean** (v19 agent): installs/upgrades clean, registry-safe, `hr.contract` correctly avoided, `account.account.company_ids` M2M, `models.Constraint`, `@api.model_create_multi`, `ir.cron` sans `numbercall/doall`, AbstractModel-inherit trap avoided.

## Validation
- `-i` (fresh DB, incl. CRA/WSIB seeds + sequences + cron + mi_tiles seed) — **clean**, registry ~63 s.
- `-u` — clean (2.2 s).
- Tests `--test-tags=/southbrook_payroll_ca` — **21/21 pass** (19 baseline + 2 new
  regression: paid-run guard, additional-tax parse). See `TEST_RESULTS.md`.
- **mi_tiles probe**: `mi_tiles_default` materialized; tiles compute live
  (`headcount=21`) — no crash.
