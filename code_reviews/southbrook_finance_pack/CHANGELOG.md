# CHANGELOG — southbrook_finance_pack

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #36)

### Fixed — financial correctness
- **NBV misstatement (HIGH-1).** `models/asset.py` `_compute_depreciation_totals`
  now sums only **`posted`** schedule lines (added `schedule_ids.posted` to
  `@api.depends`). Previously summed the entire projected schedule, collapsing
  `net_book_value` to ~0 the instant a schedule was generated.
- **Class-29 straight-line $0.01 residual (CCA-round).** `models/asset.py`
  `_generate_straight_line_schedule` rounds the per-year slice and makes the last
  depreciating year absorb the rounding residual, so the schedule sums exactly to
  the (cost-ceilinged) base.
- **Dead `post_init_hook` (F1).** `hooks.py` — `account.account` probe changed
  from removed `company_id` to v19 `company_ids` (M2M); the CoA now actually
  auto-loads on a fresh company.
- **Budget Pivot crash-on-open (F2).** `views/budget_views.xml` — removed the
  non-stored `actual_amount`/`variance` pivot measures (`_read_group` can't
  aggregate non-stored computes); pivot now measures stored `budget_amount` only.
  Actual/variance still shown per-line in the budget form list.

### Fixed — governance / multi-company
- **Filed HST return immutability (HIGH-2).** `models/hst_return.py` +
  `views/hst_return_views.xml`: period fields readonly off-draft; `action_compute`
  guarded + Compute button hidden off-draft; `_compute_totals` skips non-draft
  records so a filed snapshot can't be overwritten via an RPC period-write.
- **Uninstantiable Finance Snapshot (F3).** `security/ir.model.access.csv` grants
  manager create/unlink on `mi_tiles`; new `data/mi_tiles.xml` seeds one
  `noupdate` `Finance Snapshot` record. Menu now renders on install.
- **Cross-company tile aggregation (MEDIUM-4).** `models/mi_engine_ext.py`
  `_compute_tiles` scoped to `self.env.company` — cash, 30-day revenue, and the
  WIP/budget/HST lookups now filter by company (`company_id` / `company_ids`).

### Tests
- `tests/test_budget.py` — `account.account` search domain and stub-account create
  migrated `company_id` → `company_ids` (v19 M2M).
- `tests/test_cca_schedule.py` — `test_action_generate_schedule_persists_rows`
  rewritten to assert the corrected NBV semantics (accumulated = 0 / NBV = full
  cost when nothing posted; both track the posted slice after posting 2 years).

### Not changed (documented in REVIEW_REPORT.md — tax-law / policy, needs sign-off)
- HIGH-3 Class-29 25/50/25 CRA distribution (vs current equal-thirds).
- MEDIUM-1 AII 1.5× date-awareness (phase-out 2024-2028).
- MEDIUM-2 per-model company `ir.rule`s.
- MEDIUM-3 value-aware `state` write-guard (figures already immutable via HIGH-2).
- LOW: disposal recapture/terminal-loss; cost-ceiling vs NBV base; budget variance
  sign for revenue lines; WIP reserved-vs-consumed qty.

### Manifest
- `data/mi_tiles.xml` added to the data list.
- Version `19.0.1.0.0` → `19.0.2.0.0`.
