# Code Review — `southbrook_cmms_wms`

**Module #40 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.0.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+reliability-math; v19+data/install) →
independent source verification incl. `stock.move`/`res.groups` field probes → HEAD
baseline → real fixes + regression test → live `-i`+`-u`+tests + tile probe on isolated
DB (`ci_cmms40`, full southbrook MI + kitchen_tools dep stack staged).

## What the module does
CE-native CMMS + WMS: **MTBF/MTTR** reliability per equipment (from `maintenance.request`),
a **breakdown alert** flagging affected MOs, **service-contract** expiry tracking (cron),
an **oversize-permit** surface on stock pickings, and **landed-cost templates**. Two daily
crons (service-contract expiry, MTBF/MTTR roll-up) + an MI-dashboard `mi_tiles` snapshot.

## Verdict
**v19-clean at install** (registry-safe, correct `maintenance`/`mrp` fields, avoids the
`mrp.workcenter.equipment_ids` trap, stored graph measure, cron schema OK) and **secure**
(no sudo-on-user-id / SQL / eval; writes manager-gated). But **the service-contract cron
crashed 100% of runs** (v19 `res.groups.users`), the **expiry state was frozen in time**
(stale stored compute), and both crons **re-alerted/grew unboundedly**. Fixed **1 HIGH v19
crash + 1 CRITICAL stale-compute + 3 MED + a false UI claim + the baseline test bug**.
Baseline **1 error of 7 → 0 error of 8** (+1 regression test).

## Findings

### Fixed — crash / correctness
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **V1** | **HIGH** | **Service-contract expiry cron crashed every run** — `res.groups.users` was removed in v19; `_cron_check_expiry` hit `manager_group.users.partner_id` → `AttributeError`. The cron was never exercised by CI, so it escaped. | `manager_group.all_user_ids.partner_id` (includes managers holding the group via `implied_ids`). |
| **C1** | **CRITICAL** | **Expiry `days_to_expiry` / `state` frozen in time.** Both are `store=True` computes keyed on `date_end` (not "today"), so they **never re-fire as the calendar advances** — a contract created 90 days out reports 90 forever, `state` stays `active`, `expired` is unreachable, and the cron's window filter selects the wrong contracts. | The daily cron now `invalidate`s + force-recomputes `days_to_expiry`/`state` on the candidate set before filtering (keeps them stored for UI/search, fresh daily). |
| **TEST** | — | **Baseline test error** — `stock.move.name` was **removed in v19**; the test's `move_ids` command dict `{"name": …}` raised `KeyError: 'name'` during picking precompute. (The oversize test used the same dict but skipped earlier, hiding it.) | Dropped `"name"` from both test move dicts (`stock.move` derives its own label). |

### Fixed — cron hygiene / hardening
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **M6** | MED | **Expiry cron spammed + aborted on one bad row** — re-posted a manager alert **every day** for the whole alert window (no throttle) and had no per-row `try/except`. | Added `last_alert_date` with a **weekly** re-alert throttle; wrapped each contract in `try/except` + `_logger.exception`. |
| **M7** | MED | **MTBF cron grew unboundedly** — `_cron_generate_daily_reports` created a fresh report per equipment **every** run (~365/equipment/yr, no cleanup), and the 30-day MI tile then counted each equipment ~30× in a per-row average. | Upsert one report per `(equipment, as_of_date)` — search-then-recompute-or-create. |
| **M9** | MED | **Back-dated MTBF over-counted downtime** — for a report with `as_of_date` in the past and a still-open request, `end = today` ran past the window, so downtime could exceed `period_hours` and force runtime/MTBF to 0. | Clamp each outage to `[period_start, as_of_date]`. |
| **H3-copy** | LOW | **UI falsely claimed "Blocked N MO(s)"** — `action_block_affected_mos` only posts a warning + activity; nothing is actually blocked. | Reworded MO message + notification to "**Flagged** N MO(s) … do not run production until cleared" (honest advisory copy). |
| **M8** | LOW | **mi_tiles snapshot never populated** — no seed record, and plain users have `perm_create=0`, so the Snapshot menu was permanently empty for them. | Seeded one `noupdate` `Maintenance & Logistics Snapshot` record. |

### Documented (business-policy / cross-module / statistical — not unilaterally changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| H2 + F2 | HIGH | **Oversize-permit gate is inert AND unenforced.** No module in the dep tree provides `product_length/width/height`, so `is_oversize_load` is **always False** (the whole permit workflow never triggers); and even if it did, there is **no `button_validate` override** — it's UI-only. | Needs a dimension-field provider **and** a real validate gate (+ manager-gate the `approved` transition) — a paired feature decision, not a drive-by. Adding a dormant gate to an inert feature was judged not worth the risk. |
| H3 | HIGH | **Breakdown "block" is advisory only** — it flags MOs but imposes no hard stop; a floor operator can still run production on failed equipment. | Whether to hard-block (e.g. gate `mrp.workorder.button_start` while an open critical breakdown exists) is a policy + risk decision (the affected-MO mapping is manual/imperfect — L12 — so a blanket hard block on bad data could halt good production). |
| H4 | HIGH | **Zero-failure MTBF reports `period_hours`** (same as a 1-failure machine), not ∞/"no failures". | A statistical-presentation decision (Float can't hold ∞ cleanly); needs a sentinel/flag design. |
| H5 | HIGH | **MTTR at 24 h resolution** — `request_date`/`close_date` are `Date`, so a same-day repair counts as **0** downtime, under-reporting MTTR and inflating availability. | Needs a datetime source (stage-transition timestamps); documented as a known resolution limit. |
| L11/L12/F3/F4 | LOW | Landed-cost account found by `name ilike "Landed Cost"` (locale-fragile) + cost line needs a `product_id` (the test skips on this); breakdown affected-MO mapping is manual & operation-based; landed-cost company filter should use `company_ids` if added; two declared deps (MI, kitchen_tools) are unused. | Minor. |

## Strong positives (verified)
- **No sudo-on-user-id / SQL / eval.** Division-by-zero guarded throughout. Writes manager-gated (MTBF reports, contracts, landed-cost templates read-only for users). Crons run as `base.user_root`.
- **Avoids the `mrp.workcenter.equipment_ids` v19 trap** (breakdown carries its own `workcenter_id`); stored graph measure; correct `ir.cron` schema; `mi_engine_ext` is a NEW model (AbstractModel-inherit trap avoided); `stock.move.quantity_done`-removal handled defensively.
- Expiry cron does **not** mutate state (idempotent).

## Validation
- `-i` (fresh DB, full MI + kitchen_tools dep stack) — **clean**, registry ~67 s.
- `-u` — clean (2.2 s).
- Tests `--test-tags=/southbrook_cmms_wms` — **8/8 pass / 0 error** (landed-cost test
  skips by design on the bare-DB landed-cost-product gap), from a baseline of 1 error
  of 7. See `TEST_RESULTS.md`.
- **mi_tiles probe**: `mi_tiles_default` materialized; tiles compute live — no crash.
