# CHANGELOG — southbrook_quality

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #38)

### Fixed — statistical correctness
- **Cpk uses sample σ (S1, CRITICAL).** `models/cpk_report.py` — `STDDEV_POP`
  → `STDDEV_SAMP` (Bessel n−1) in all three places. Population σ understated
  variation and inflated Cpk, silently passing incapable processes. The existing
  `COALESCE(…,0)`+`CASE` still yields a conservative Cpk 0 for n=1.
- **Configurable Cpk window wired (S5).** `init()` reads
  `ir.config_parameter southbrook_quality.cpk_window_days` (int-cast, injection-safe)
  and bakes it into the view DDL; the window was previously hardcoded to 30 days
  and the documented parameter was dead.

### Fixed — NCR governance / integrity
- **State-transition write guard (N1, HIGH).** `models/ncr.py` — `write()` now routes
  every `state` change through `_ensure_transition`; guarded actions bypass via the
  `_ncr_state_ok` context flag. Closes raw-`write({"state":"released"})` laundering
  that skipped quarantine, the disposition reason, and `closed_at`.
- **Critical use-as-is release needs a manager (N2, HIGH).** `action_release` requires
  `group_southbrook_quality_manager` when `severity == "critical"`.
- **Explicit `opened_at` SLA start (TTC).** Added a writable `opened_at`
  (`default=now`); `_compute_time_to_close_hours` computes from it (falling back to
  `create_date`) with a `max(0.0, …)` clamp. Fixes a negative/non-deterministic
  time-to-close — v19 silently ignores `write()` on the magic `create_date`.

### Fixed — SPC
- **OOS→NCR idempotency (C1).** `models/spc_sample.py`
  `action_create_ncr_if_oos` skips samples that already have a linked NCR.

### Tests
- `tests/test_cpk_view.py` — flush the ORM before querying the SQL-view report.
- `tests/test_ncr_workflow.py` — back-date `opened_at` (not the un-writable
  `create_date`); +2 regression tests: `test_raw_write_state_is_guarded` (N1),
  `test_critical_release_requires_manager` (N2).

### Not changed (documented in REVIEW_REPORT.md — statistical-scope / policy)
- S2 "Cpk" is really Ppk (overall σ, no subgroups); N3 no segregation of duties;
  S3 MAX(usl)/MIN(lsl) tolerance widening; S4 zero-variance → Cpk 0; A1 no
  multi-company rule on supplier_defect; X1 refresh-view DDL reachable by readers;
  M1 mi_tiles action lacks res_id; M2 FPY can go negative.

### Manifest
- Version `19.0.1.0.0` → `19.0.2.0.0`.
