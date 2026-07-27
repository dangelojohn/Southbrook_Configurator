# Code Review — `southbrook_quality`

**Module #38 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.0.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+SPC/Cpk-math; v19+data/install) →
independent source verification incl. hand-checked Cpk formula + live `create_date`
write probe → HEAD baseline → real fixes + regression tests → live `-i`+`-u`+tests on
isolated DB (`ci_qual38`, full southbrook MI + kitchen_mrp dep stack staged).

## What the module does
CE-native quality control (no Enterprise `quality_control`): **NCR** (non-conformance
reports) with a draft→quarantine→{rework|scrap|released|cancelled} state machine +
disposition gate, **SPC** samples (per-dimension measurements at a workcenter), a
SQL-view-backed rolling **Cpk** report, and **supplier-defect** tracking. Publishes a
`mi_tiles` snapshot for the MI dashboard.

## Verdict
**v19-clean** (v19 agent: installs/upgrades clean, registry-safe, no traps; the Cpk/
SPC reporting is correctly SQL-view-backed so graph measures aggregate) and **secure**
(no sudo / SQL-injection / eval; no portal exposure; master data manager-gated; and —
unlike finance_pack/payroll_ca — it **correctly seeds its mi_tiles singleton**). The
defects were in **statistical correctness, NCR governance, and two pre-existing test
failures that masked real product bugs**. Fixed **1 CRITICAL + 2 HIGH + 2 MED + 2
product bugs behind the baseline failures**. Baseline **2 failed of 14 → 0 failed of
16** (+4 regression/repaired tests).

## Findings

### Fixed — correctness / integrity
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **S1** | **CRITICAL** | **Cpk computed with population σ (`STDDEV_POP`, ÷n) not sample σ.** Population σ understates process variation → **inflates Cpk**, so an incapable process reads as capable and **silently passes bad parts** (up to 1.41× overstatement at n=2; a true Cpk 0.94 reports 1.33 and clears an AIAG 1.33 gate). | `STDDEV_SAMP` (Bessel n−1). The n=1 NULL is already absorbed by the existing `COALESCE(…,0)`+`CASE` → conservative Cpk 0, so the docstring's stated reason for POP didn't hold. |
| **TTC** | HIGH | **`time_to_close_hours` computed off `create_date` → tiny negative / non-deterministic** (pre-existing test failure). v19 **silently ignores `write()` on `create_date`** (verified by live probe: value unchanged), and `create_date` is a DB-transaction timestamp that can trail the app-server `closed_at` (clock skew) → negative. | Added an explicit **writable `opened_at`** (`default=now`) as the SLA start; compute from it (falling back to `create_date`) with `max(0.0, …)` clamp. |
| **CPK-flush** | MED | **Cpk report returned an empty row** (pre-existing test failure). The report is a SQL view reading the `spc_sample` **table** directly; ORM-pending sample INSERTs aren't flushed before the view SELECT (no ORM-level dependency links them). | Test flushes before querying (production commits between sample entry and report view, so product is unaffected — this was a test-harness gap that nonetheless exposed the view's flush semantics). |
| **C1** | MED | **`action_create_ncr_if_oos` not idempotent** → a re-run of the OOS sweep spawns duplicate NCRs for the same sample. | Skip samples that already have a linked NCR (`rec.ncr_ids`). |
| **S5** | MED | **`cpk_window_days` config param was dead** — the header + `action_refresh_view` claim the rolling window is configurable, but the SQL hardcoded `INTERVAL '30 days'` and the param was read nowhere. | `init()` now reads the param (int-cast, injection-safe) and bakes it into the view DDL; `action_refresh_view` picks up a changed value. |

### Fixed — governance / security
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **N1** | **HIGH** | **NCR state launderable via raw `write()`.** The transition graph + mandatory-disposition gate lived only in the action buttons; a quality user (has `perm_write`) could `write({"state":"released"})` via `call_kw` — skipping quarantine, the disposition reason, and `closed_at` (no audit trail, no time-to-close). | `write()` override routes every state change through `_ensure_transition` (guarded actions set a private context flag to bypass the re-check; same-state no-op writes are skipped). |
| **N2** | **HIGH** | **Critical-NCR "use-as-is" release needed no elevated sign-off.** Any quality user could `action_release` a `severity='critical'` NCR — shipping a known safety-relevant defect on a free-text reason. | `action_release` requires `group_southbrook_quality_manager` when `severity='critical'`. |

### Documented (business-policy / statistical-scope — not unilaterally changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| S2 | MED | **Index labelled "Cpk" is actually Ppk** — it pools all individuals over the window (overall σ), not within-subgroup short-term σ (R̄/d₂). No subgroups, no X-bar/R chart, no control limits. | Ppk ≤ Cpk (conservative direction). Rename to `ppk` or add subgrouping — a statistical-model decision. |
| N3 | MED | **No segregation of duties** — the raiser (`responsible_user_id` defaults to creator) can disposition/close their own NCR. | Add a raiser≠closer check if the quality system requires it. |
| S3/S4 | LOW | Cpk uses `MAX(usl)`/`MIN(lsl)` → widens the band if spec limits change mid-window; zero-variance forces Cpk 0 (conservative but flags a perfect process as failing). | Group so limits are consistent; treat σ=0 as a gauge-resolution review. |
| A1/X1/M1/M2 | LOW | `supplier_defect` has no multi-company record rule (`company_id` exists, single-company OK for now); `action_refresh_view` runs `CREATE OR REPLACE VIEW` reachable by any reader via RPC (idempotent, harmless — should be manager-gated); the `mi_tiles` action opens a form with no `res_id` (blocked empty form vs the seeded singleton — UX); `quality_fpy_30d` counts all NCRs incl. cancelled and can go negative. | Minor robustness/UX. |

## Strong positives (verified)
- **No sudo / eval; SQL injection-safe** (only `self._table`/int-window interpolated); div-by-zero guarded; UTC rolling-window correct; terminal-state idempotency (empty allowed-sets).
- **Correctly seeds its `mi_tiles` singleton** (via `mi_engine_ext_views.xml`) — the exact fix finance_pack/payroll_ca were missing.
- **v19-clean**: SQL-view-backed report avoids the non-stored-measure pivot trap; `models.Constraint`; `@api.model_create_multi`; `<list>`/`<chatter/>`; `stock.lot` (correct v19 name); no `mrp.workorder` dep (documented CE-safety); AbstractModel-inherit trap avoided.

## Validation
- `-i` (fresh DB, full MI + kitchen_mrp dep stack) — **clean**, registry ~63 s.
- `-u` — clean (2.0 s).
- Tests `--test-tags=/southbrook_quality` — **16/16 pass**, from a baseline of 2 failed
  of 14. See `TEST_RESULTS.md`.
