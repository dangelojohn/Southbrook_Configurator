# Code Review — `southbrook_mes_mps`

**Module #39 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.0.1 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+MES/MPS-math; v19+data/install) →
independent source verification incl. traced OEE calc + `res.groups` field probe →
HEAD baseline → real fixes + test repair → live `-i`+`-u`+tests + tile probe on
isolated DB (`ci_mes39`, full southbrook MI + kitchen_mrp + workcenters dep stack).

## What the module does
CE-native MES/MPS (no Enterprise `mrp_mps`/`mrp_workorder`): a rolling **13-week MPS**
(master production schedule per product), **OEE** snapshots per workcenter (from the CE
`mrp.workcenter.productivity` loss log), weekly **workcenter capacity**, and a live
**Bottleneck report** ranking workcenter load. Two daily crons (OEE roll-up, bottleneck
report) and an MI-dashboard `mi_tiles` snapshot.

## Verdict
**v19-clean at the structural level** (registry-safe, correct mrp/stock field usage,
`models.Constraint`, CE-safe `mrp.workorder` states, cron schema, AbstractModel trap
avoided) and **secure** (no sudo/SQL/eval, crons preserve history — no delete-all,
master data manager-gated). But **three defects silently corrupted the numbers users
see** and **two deferred-path crashes** would fire the first time the bottleneck cron
ran or the MPS pivot opened. Fixed **2 HIGH v19 + 1 HIGH OEE + 1 HIGH display + 1 MED +
seed + the baseline test bug**. Baseline **1 failed of 8 → 0 failed of 8**.

## Findings

### Fixed — v19 / runtime crashes
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **V1** | **HIGH** | **Daily bottleneck cron crashed every run** — `res.groups.users` was **removed in v19** (now `user_ids`); `cron_create_daily_report` hit `sup_group.users` → `AttributeError` once a top bottleneck existed. | `sup_group.user_ids`. |
| **V2** | **HIGH** | **MPS Workbench pivot crashed on open** — `to_supply_qty` (a **non-stored** compute) was a pivot `type="measure"`; `_read_group` can't aggregate non-stored → error toggling to pivot. | Dropped it from the pivot (kept stored `forecast_qty`); it remains a summed column in the list view, which renders non-stored computes fine. |

### Fixed — computation / display correctness
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **O1** | **HIGH** | **Automated OEE was always 0.** The `cron_oee_daily` roll-up hardcoded `units_produced/target/rejected = 0`, so `_compute_oee` forced Performance and Quality to 0 → **every** cron snapshot read OEE 0% / "unacceptable" regardless of real output, and dragged `mi_tiles.avg_oee_last_7d` toward 0. The headline MES metric was dead. | Derive real units from the workorders the day's `mrp.workcenter.productivity` rows reference (`qty_produced` / `qty_production`). |
| **PCT** | **HIGH** | **Every load/forecast % displayed 100× too large.** `*_pct` fields store a 0–100 value but views rendered them with `widget="percentage"` (which multiplies by 100 for display) → a 150%-loaded workcenter showed "**15000%**". Stored values + threshold logic were correct; only the display. | Removed `widget="percentage"` from the five `*_pct` view fields. **Kept it on the OEE fields** (`availability/performance/quality/oee/avg_oee_last_7d`), which correctly store 0–1 fractions. |
| **B2** | **MED** | **Inline bottleneck fallback overcounted load.** When no capacity row exists, it summed `mrp.workorder.duration_expected` with **no state filter** (incl. `done`/`cancel`), disagreeing with the capacity model's `('blocked','ready','progress')` filter for the same workcenter. | Applied the same state filter to the fallback. |
| **TILE** | LOW | **MES Snapshot menu opened empty** — `mi_tiles` had `perm_create=1` (no F3 ACL defect) but **no seed record**, so nothing instantiated the singleton the MI dashboard reads. | Seeded one `noupdate` `MES/MPS Snapshot` record. |
| **TEST** | — | **Baseline test failure** (`test_top_bottleneck_is_highest_load`): the fixture seeded `capacity.planned_hours`, a **computed** field (from `mrp.workorder`), which was overwritten to 0 → all three lines' `load_pct` read 0 → `max` returned the first (low), not high. | Rewrote the fixture to stage real workorders (10h/30h/60h → 25%/75%/150% load); the bottleneck ranking logic itself was correct. |

### Documented (algorithmic-design / policy — needs owner review, not unilaterally changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| M1 | MED | **No time-phased projected-on-hand.** `_compute_to_supply` subtracts the **current** total on-hand independently in **every** one of the 13 weekly rows (no `POH_week = POH_prev + supply − demand` cascade), so net requirements are wrong for weeks ≥2 (100 on hand + 40/wk forecast → every week shows "−60, no production needed"). | A cross-record cumulative cascade in a stored compute — a core MPS-semantics redesign warranting owner sign-off. |
| B1 | LOW | Header "Top Bottleneck" ranks by `load_pct` but the line list `_order` is `bottleneck_score desc` (load × routing-dependency count) → top-of-list can differ from the header. | Decide which metric is authoritative. |
| C1 | LOW | Crons have no per-row `try/except` — one bad workcenter/row rolls back the whole daily run. | Guard per-workcenter. |
| — | LOW | MPS demand bucketed by `order_id.date_order` (placed date) not commitment/delivery date; `date_order` Datetime vs naive week_start (UTC edge); `mi_tiles` `perm_write=1` for plain users; a dead `search_default_group_by_product`. | Minor. |

## Strong positives (verified)
- **No sudo / SQL / eval.** Crons **append/upsert** (history preserved) — no delete-all-recreate; no `commit()` (test-cursor safe). Master data manager-gated; `group_mes_user` implies `base.group_user` (standard direction).
- **OEE factor math correct**: Availability `(planned−downtime)/planned` clamped [0,1]; **Performance clamped ≤1.0** (prevents the >100% "super-machine" bug); Quality clamped; all divisors zero-guarded (hand-traced to world_class 0.9487).
- **13-week / ISO-Monday MPS window correct** (no off-by-one, idempotent, UNIQUE key).
- **v19-clean**: `res.groups.user_ids` (now), CE `mrp.workorder` states, `mrp.workcenter.productivity`, `models.Constraint`, `@api.model_create_multi`, `ir.cron` schema, AbstractModel-inherit trap avoided, no `obj()`-in-`<value>`.

## Validation
- `-i` (fresh DB, full MI + kitchen_mrp + workcenters dep stack) — **clean**, registry ~66 s.
- `-u` — clean (2.4 s).
- Tests `--test-tags=/southbrook_mes_mps` — **16/16 pass** (8 post-tests), from a
  baseline of 1 failed of 8. See `TEST_RESULTS.md`.
- **mi_tiles probe**: `mi_tiles_default` materialized; tiles compute live — no crash.
