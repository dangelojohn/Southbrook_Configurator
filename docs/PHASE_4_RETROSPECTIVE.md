# Phase 4 — Retrospective

**Drafted:** 2026-06-11
**Status:** 6 of 8 Phase 4 deliverables shipped (5 of 6 in code; 1 live in prod)
**Source brief:** `CLAUDE.md` §8 Phase 4 (MRP polish + cut-list bridge)

This document mirrors `docs/PHASE_3_PLAN.md`'s format but writes
backwards from shipped commits rather than forwards to planned ones.
It captures what landed, what didn't, what was harder than expected,
and what should be tackled next.

---

## What shipped (6 sprints)

| Sprint | Item | Commit | Effort plan | Effort actual |
|---|---|---|---:|---:|
| 1 | Accucutt cut-list bridge endpoints + contract | `f986c98` | 1d | <2h |
| 2 | Send-to-Manufacturing button | `27eb2c9` | 0.5d | 1h |
| 3 | Per-line BoM breakdown panel | `fed3fcd` | 1d | 1h |
| 4a | Shop Copy QWeb report — panel cut list section | `bb71b05` | 0.5d | 30m |
| 4b | Door Order QWeb report — B2 dims + series totals | `793762c` | 0.5d | 30m |
| 5 | Multi-currency awareness on catalog endpoint | `276d3d4` | 2d | 1h |

**Total:** 5.5 days budgeted → ~6 hours actual. Compression came from
the same patterns Phase 3 used: leaning on existing infrastructure
(B2 fields, OCA/Odoo helpers, the established `/api/v1/` auth +
idempotency machinery) instead of rebuilding.

---

## What didn't ship

| Item | Why |
|---|---|
| Prodboard 18-element parametric carcass grammar | Massive (~5-10d in the plan); doesn't fit a session-end slot; needs its own scope conversation. Two of 18 element types exist in `kitchen_viewport.esm.js` today (hinge_block, drawer-derivatives). |
| Demo seed replay (5-10 case-study orders) | Content-heavy: needs decisions on which orders to replay, screenshot capture cadence, and where the investment-committee artifact lives. |

Both are explicitly Phase 4 deliverables from `CLAUDE.md` §8 but were
deferred deliberately.

---

## Test coverage added

| Test file | Tests | Module |
|---|---:|---|
| `test_cutlist_nesting.py` | 7 | `southbrook_api` |
| `test_send_to_manufacturing.py` | 4 | `southbrook_estimating_website` |
| `test_bom_payload_per_line.py` | 2 | `southbrook_estimating_website` |
| `test_multi_currency.py` | 2 | `southbrook_estimating_website` |

15 new HttpCase + TransactionCase tests covering the 6 sprints.
Module test counts:
- `southbrook_api` 9 → 16 (+7)
- `southbrook_estimating_website` 29 → 37 (+8)

---

## Bug fixes shipped alongside

| Fix | Root cause | Commit |
|---|---|---|
| `_get_cut_constants` PLM seam restored | Parallel session dropped the method; `super()._get_cut_constants()` raised AttributeError | `bb918ba` |
| Dealer-portal callable-selection handling | Odoo 19 related Selection fields expose `.selection` as a function | `a931404` |
| Marathon CSV import counter inverted | Post-create search-back always counted "updated" instead of "created" | `346fdbc` |
| Tradesperson Tier 3 catalog pricing | Odoo 19 made `_compute_price_rule.currency` kwarg-only + dynamic-variant guard hid the pricelist path | `094b7e3` |
| Prod hardware-catalog dep cache cleared | Stale `ir_module_module_dependency` row | (operational, not commit) |
| TestCatalogMetadataSeed × 2 | Odoo 19 tightened product.template ACL + lang validation | `d0534e4` |
| TestAuditPhase2 test_02 | Premium price_extra deltas live in `configurator_ux`, not estimating | `d0534e4` |

After fixes, test suite was green across:
- `southbrook_estimating` 163/163
- `southbrook_hardware_catalog` 41/41
- `southbrook_plm` 16/16
- `southbrook_dealer_portal` 10/10
- `southbrook_estimating_website` 29/29

---

## Deploy state at session end

| Component | Live in prod | On Forgejo | Notes |
|---|---|---|---|
| Phase 3 (13/13 items) | ✅ | ✅ | Live + verified |
| Phase 4 Sprint 1 (Accucutt bridge) | ✅ | ✅ | `/api/v1/cutlist/<id>/envelope` returning 401 as designed |
| Phase 4 Sprints 2-5 | ❌ | ✅ | Blocked behind a parallel-session XML bug — see below |
| 4 of 7 bug fixes | ✅ | ✅ | The PLM-seam, dealer-portal, Marathon-CSV, and pricelist fixes are in prod via earlier deploys |

### Deploy block details

`southbrook_manufacturing_intelligence/views/pm_kanban_inherit.xml`
attempts an xpath at
`//div[hasclass('o_sb_pm_dash_card_h')]` that doesn't match anything in
the inherited parent view. Every `odoo -u <anything>` cold-load hits
the broken view first and refuses to advance. The deploy script
(commit `7bb7838`, parallel session) correctly aborts before
restarting prod, leaving the previous version live.

Resolution: the parallel session that introduced the inherited view
needs to fix the xpath OR pin the inherit_id to a base view that
actually has `o_sb_pm_dash_card_h`. Not safe for me to guess at —
the original intent isn't documented.

---

## What was harder than expected

1. **Odoo 19 API churn** — three separate breakages from v18 patterns:
   - `_compute_price_rule(...)` made `currency` keyword-only after `*`
   - `sale.order.line.product_uom` renamed to `product_uom_id`
   - `product.template` portal ACL tightened (record-rules now block
     even `base.group_portal` from arbitrary template reads)
2. **`getattr` not in QWeb safe-eval** — KeyError on first attempt at
   the Door Order enrichment; had to switch to direct field access
   (`line.sb_door_count` works because the B2 field always exists on
   `sale.order.line` when estimating is loaded).
3. **Parallel-session collision** — three deploys this session blocked
   on `ir_module_module` serialization or downstream XML view
   inheritance errors that I didn't author. Working in a shared
   worktree with another active session is real overhead. Pattern
   documented in `docs/WORKTREES.md`; we should follow it more
   strictly next time (one worktree per session).

---

## What was easier than expected

1. **Accucutt bridge** — model-layer envelope code already existed
   (`sb.cutlist.to_nesting_envelope` / `from_nesting_result`); Sprint 1
   was 90 % a HTTP-surface wrapper.
2. **Per-line BoM breakdown** — B2's `sb_panel_count` /
   `sb_door_count` / `sb_width_mm` fields landed in a prior session
   exactly the right shape for the panel display. Surface-only work.
3. **Multi-currency awareness** — Odoo's `res.currency._convert` does
   all the heavy lifting; the catalog endpoint already had a website
   currency resolution + rounding step. ~50 lines of code total.

---

## Recommendations for the next Phase 4 session

1. **Clear the parallel-session deploy block first.** Anything new
   stacks behind it until the `pm_kanban_inherit.xml` xpath is fixed.
2. **Then 18-element grammar.** It's the big remaining differentiator
   and needs a fresh, focused session. Scope conversation before
   coding: which 4-5 element types ship first? Probably `oven`,
   `drawer` (refactor the existing hinge_block analog), `delimiter`,
   and `L_profile` — the highest-frequency in real cabinets per the
   manifest §5.2 frequency table.
3. **Demo seed replay last.** Once the 18 element types support the
   typical case-study cabinets, the 5-10 replay orders render against
   real geometry, not procedural stand-ins. Replay BEFORE that and
   you commit to re-running it later anyway.

## Outside Phase 4 (still backlog)

Owner-decisions and content gates from the previous "what is pending"
report are unchanged; this retrospective doesn't move those forward.
