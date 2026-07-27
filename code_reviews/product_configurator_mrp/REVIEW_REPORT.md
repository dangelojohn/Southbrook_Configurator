# Code Review & Repair Report — `product_configurator_mrp`

**Module:** Product Configurator Manufacturing (OCA, Southbrook-modified) · **Version:** 19.0.1.0.0 → **19.0.1.1.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 CE · **Queue:** #7 of 46 (Tier 1; deps `mrp`, `product_configurator`)
**Method:** combined audit agent (v19/security/perf) + independent verification + live overlay install/test on Odoo 19 CE.

## Executive Summary
Small (~1,330 LOC) OCA bridge: generates `mrp.bom` from a configured variant. Diverges from OCA in 3 files (a JS view — which is actually a **v19 port FIX** — and 2 tests). **Clean on every v19 axis** (no `_sql_constraints`/`name_get`/`<tree>`/`attrs=`/legacy-JS/`sudo`/`cr.execute`; modern ESM controllers; `column_invisible="parent.…"` verified correct against core). No CRITICAL issues. Two HIGH defects were found and fixed: a silent BoM data-corruption bug and an ACL/UI mismatch that broke the Configure feature for its intended users.

## Original Issues Found
| # | Sev | Finding |
|---|-----|---------|
| 1 | **HIGH** | ACL/UI mismatch: the Configure/Reconfigure buttons show to all internal users (`group_product_configurator`, implied by `base.group_user`), but the wizard ACL (`access_product_configurator_mrp`) was **manager-only** → any MRP user clicking gets `AccessError`. Broken feature. |
| 2 | **HIGH** | Data corruption in `create_get_bom` (`models/product_config.py`): the "common" parent-BOM-line branch computed the onchange into `values2` then **discarded it** — `get_vals_to_write(values=values, …)` used the stale outer `values` → wrong `mrp.bom.line` data. Untested branch (OCA-original bug). |
| 1b | MED | Dead `group_product_configurator_mrp` group — defined, never referenced. |
| 3 | MED | N+1 `operation_ids.copy()` loop when propagating parent-BOM operations. |
| 4 | MED | `get_onchange_specifications`/`sanitized_spec` recomputed per loop iteration (constant across the loop). |
| 5 | MED | TOCTOU on the search-then-create existing-BoM check → duplicate BOMs under concurrent submits. |
| 6 | LOW | Dead `"qweb"` manifest key (unprocessed since several majors). |
| 7/8 | LOW | `sanitized_spec` mutates its input; `config_session_id`/`config_set_id` unindexed (future). |

### Clean (verified): all 13 v19 axes; the diverged `mrp_production_views.xml` (a correct v19 fix — drops the stale `[2]` xpath index since v19 collapsed the duplicate create-button slot); `safe_eval` only on admin-authored action context (not user input).

## Repairs Completed
1. **#2:** `get_vals_to_write(values=values2, …)` — the "common" BOM line now uses its own onchange result. (Correctness/data-integrity.)
2. **#1:** widened `access_product_configurator_mrp` to `product_configurator.group_product_configurator` — the wizard is now usable by the same audience the buttons target.
3. **#6:** removed the dead `"qweb"` manifest key.

### Documented (not changed)
- #1b dead group (removable — cosmetic).
- #3/#4 perf (batch `copy_data`+single create; hoist the specs computation) — OCA-engine tidy-ups, low urgency.
- #5 TOCTOU — recommend an advisory lock, NOT a unique constraint (core `mrp.bom` legitimately allows multiple BOMs per product). Mirrors the hermes_bom advisory-lock fix.
- #7/#8 cosmetic/future.

## Files Changed
3 modified (`__manifest__.py`, `models/product_config.py`, `security/ir.model.access.csv`).

## Database / Security / Performance
No schema change. Security: fixed the broken-feature ACL (a functional fix, not a privilege change — the buttons already targeted these users). Perf items documented for follow-up.

## Testing Results
_See `TEST_RESULTS.md`._ Installs cleanly on v19; 2/3 tests pass; the 1 error is `TestMrp.setUpClass` → `product_configurator.bmw_2_series` demo-data-not-loaded (inherited from the parent module's test fixture; the local container doesn't load demo data — environment limitation, not a defect). No regressions from the fixes. Wizard-model ACL confirmed widened in the DB.

## Remaining Risks
1. The #2 "common BOM line" branch has no test coverage (needs a parent-BOM-without-config_set fixture + demo data) — add coverage in a demo-enabled env.
2. #5 BoM-duplication race under concurrent configuration — apply the advisory lock before high-concurrency use.

## Recommendations
Upstream #1/#2/#6 to the OCA fork; add the advisory lock (#5) and the untested-branch coverage; run the demo-enabled suite before deploy.
