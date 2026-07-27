# Code Review — `southbrook_finance_pack`

**Module #36 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.0.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+correctness; v19+data/account-API) →
independent source verification → HEAD baseline → real fixes + test repairs → live
`-i`+`-u`+tests + tile-render probe on isolated DB (`ci_fin36`, full southbrook MI
dep stack staged).

## What the module does
CE-native Canadian accounting pack (Enterprise `account_asset` is unavailable on
this build): a **CCA capital-asset register** (declining-balance + Class-29
straight-line, half-year rule, AII, cost ceilings) with generated depreciation
schedules; a **quarterly HST return** (output tax / ITC / net owing from the
ledger); an **annual budget vs actual**; a **WIP report**; and a computed
**"Finance Snapshot"** dashboard (cash / WIP / HST / 30-day revenue tiles). A
`post_init_hook` auto-loads the `l10n_ca` chart of accounts on a fresh company.

## Verdict
The module is **install-clean and free of injection / sudo-misuse / raw-SQL /
eval** (no controllers, no cron, all `@api.depends` resolve, `models.Constraint`
used, `@api.model_create_multi` throughout). The defects were concentrated in
**financial-computation correctness, v19 `account.account` API drift, and
governance of filed figures** — several of which silently produced *wrong
numbers* or *dead features* rather than crashing. Fixed **2 HIGH + 3 (F1/F2/F3)
runtime/correctness + 1 MEDIUM** and repaired the CCA rounding. Baseline **1 fail
+ 2 err of 15 → 0 fail 0 err of 15**.

## Findings

### Fixed — correctness / v19
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **HIGH-1** | **HIGH** | **Net Book Value collapsed to ~0 the instant a schedule was generated.** `_compute_depreciation_totals` summed **every projected** schedule line into `accumulated_depreciation`, ignoring the `posted` flag — so `net_book_value = cost − full-future-schedule ≈ 0` even though *zero* depreciation had been taken. Any statement reading these two stored, prominently-displayed fields got a materially misstated book value. | Sum **only `posted` lines**; added `schedule_ids.posted` to `@api.depends`. NBV now = cost − depreciation actually taken. Test that baked in the wrong behavior rewritten to post lines and assert the correct progression. |
| **F1** | **HIGH** | **`post_init_hook` was dead** — `hooks.py` probed `account.account` with the v19-removed `company_id` field; the leaf raised, the broad `except` swallowed it, and the CoA was **never auto-loaded on a fresh company** (the hook's entire purpose). | `company_id` → `company_ids` (v19 M2M). |
| **F2** | **HIGH** | **Budget Pivot crashed the web client on open.** The pivot declared `actual_amount` and `variance` as `type="measure"`, but both are **non-stored, search-based computes** — `_read_group` cannot aggregate a non-stored field → immediate error opening the Budget Pivot menu. | Dropped the two non-stored measures (keeping stored `budget_amount`). They remain visible per-line in the budget form's embedded list, which renders non-stored computes fine. (Storing `actual_amount` was rejected: it depends on period/account, not on the AML it sums, so it would silently go stale.) |
| CCA-round | MED | **Class-29 straight-line left a permanent $0.01 UCC.** `per_year = base/n` with `10000/3` → `3333.33 × 3 = 9999.99`, mis-stating the final year and never fully depreciating. | Round the per-year slice and make the **last depreciating year absorb the residual** so the schedule sums **exactly** to base. |

### Fixed — security / governance / multi-company
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **HIGH-2** | **HIGH** | **Filed HST figures were silently mutable.** The totals are `store=True` keyed `@api.depends("period_from","period_to",…)`; editing the period on a **filed/paid** return re-fired the compute and overwrote the officially-remitted numbers, and the **Compute** button / `action_compute` had no state guard (recompute pulled in any invoice back-dated into the period after filing). A filed CRA return must be immutable. | 3-layer lock: (1) period fields `readonly` once `state != draft` (view); (2) `action_compute` raises on non-draft + Compute button hidden off-draft; (3) **`_compute_totals` itself skips non-draft records** so even an RPC period-write can't overwrite the filed snapshot. |
| **F3** | **MED** | **"Finance Snapshot" dashboard was uninstantiable** — `mi_tiles` had `perm_create=0` for **both** groups and **no seed record**, so the menu was permanently empty and its New button raised `AccessError`. The whole feature was dead as shipped. | Granted manager create/unlink; seeded one `noupdate` `Finance Snapshot` record so the dashboard renders on install. |
| **MEDIUM-4** | **MED** | **Dashboard tiles summed all companies' ledgers.** Cash-position and 30-day-revenue searches (and the WIP/budget/HST lookups) applied **no company filter** → on a multi-company DB every company's cash & revenue landed in the current company's snapshot. | Scoped the entire `_compute_tiles` to `self.env.company` (AML `company_id`, `account.account` `company_ids`, and the WIP/budget/HST record searches). |

### Documented (business-policy / tax-law — needs owner/accountant sign-off, not unilaterally changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| HIGH-3 | HIGH | **Class-29 straight-line distributes 33⅓/33⅓/33⅓, not the CRA 25/50/25.** `rate_pct=50` on the class is ignored by the straight-line path and the half-year rule is never applied, so each *individual year's* CCA on Class-29 manufacturing/automation equipment is mis-stated (the 3-year *total* is correct after the rounding fix). The correct CRA schedule is 25 % (half-year) / 50 % / 25 %. | A tax-filing distribution change touching the schedule generator **and** the asserting test — deferred to the owner/accountant to confirm before altering filed CCA math. |
| MEDIUM-1 | MED | **AII 1.5× is not date-aware.** Year-1 CCA unconditionally applies `base·rate·1.5` whenever the class flag is set, ignoring `acquisition_date`. The enhanced first-year allowance is phasing out (reduced 2024-2027, gone 2028) → a 2026 acquisition over-deducts. | Key the boost off `acquisition_date`, not a static class flag. |
| MEDIUM-2 | MED | **No `ir.rule` anywhere → no multi-company row isolation.** A finance-group member in a multi-company DB can read/write HST returns, budgets, assets, WIP across *any* company. (Positive: models are NOT open to `base.group_user` — exposure is strictly cross-company within the finance group.) | Add per-model company record rules. |
| MEDIUM-3 | MED | **`state` reachable by raw `write()`** — the file/pay actions' "only draft can be filed" guards are advisory; a direct `write({"state":"paid"})` bypasses them. (The *figures* are now immutable via HIGH-2, closing the material-integrity risk.) | Add a value-aware `write()` transition guard. |
| LOW×4 | LOW | Disposal is a tax no-op (no proceeds/recapture/terminal-loss); cost-ceiling caps the CCA base but NBV uses the uncapped cost (inconsistent for a $45k Class-10.1 vehicle); budget variance sign assumes expense accounts (inverts for revenue lines); WIP uses reserved not consumed qty for `confirmed` MOs. | v1 scope gaps, documented. |

## Strong positives (verified by both agents)
- **HST sign conventions correct**: `collected = −Σ(out tax balance)`, `ITC = +Σ(in tax balance)`, `net = collected − ITC`; refunds net by natural sign; taxable-sales base from `tax_ids!=False, tax_line_id=False` lines. No double-count, no missing bucket, no re-rounding of tax-engine amounts.
- **Declining-balance CCA math correct**: half-year ×0.5, `balance×rate` thereafter, `min(cca,balance)` clamp prevents negative UCC (verified against a textbook Class-8 series).
- **v19-clean**: `models.Constraint` (not `_sql_constraints`), `@api.model_create_multi`, no `groups_id`/`check_access_rights`/`name_get`/`attrs=`/`<tree>`/`t-raw`, `groups.xml` omits the dropped `category_id`, correct `try_loading("ca", …)` hook signature, every `account.move.line` field (`parent_state`, `tax_line_id`, `tax_ids`, `display_type`, `balance`) traced to v19 core.
- `mi_engine_ext` correctly declares a **new** model rather than `_inherit`-ing the `southbrook.mi.engine` AbstractModel (avoids the v19 AbstractModel-inherit trap). `post_init_hook` idempotent + fully exception-guarded.

## Validation
- `-i` (fresh DB `ci_fin36`, full MI dep stack) — **clean install**, registry ~66 s.
- `-u` — clean (2.1 s).
- Tests `--test-tags=/southbrook_finance_pack` — **15/15 pass**, from a baseline of
  1 fail + 2 err. See `TEST_RESULTS.md`.
- **F3 probe**: `mi_tiles_default` record materialized; tiles compute live
  (`cash=4190.93, rev30=76324.0`) with no crash.
