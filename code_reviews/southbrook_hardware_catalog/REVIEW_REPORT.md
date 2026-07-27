# Code Review — `southbrook_hardware_catalog` (Module #14, Tier 3)

**Version:** 19.0.2.1.0 → **19.0.2.2.0**
**Reviewed:** 2026-07-11
**Scope:** ~1411 LOC — product.template/product.product extensions, `southbrook.hardware.brand`, `southbrook.hardware.catalog` (AbstractModel resolution service), a CSV-import wizard, seed data (XML + `hardware_map.json`), tests. No controllers.
**Method:** Two independent parallel audits (v19-compat + code; security + performance); every HIGH/MEDIUM claim re-verified against source before editing.

---

## Executive Summary

Marathon Hardware catalog + the per-carcass hardware-**resolution** service that BoM generation calls. Both audits found it **notably clean**: **v19-compat CLEAN** (`models.Constraint`, `type="consu"`+`is_storable`, `<list>` views, stored-related selection done right, all xmlids resolve), and **security has no attack surface** — **no controllers, no `sudo()`, no `eval`/SQL, no server-side URL fetch (no SSRF), ACL complete and manager-scoped**. The real defects are a **hot-path N+1** and **three correctness/robustness bugs in the CSV-import wizard** (one of which silently rejected valid data).

Fixed: **1 HIGH (resolve N+1), 3 MEDIUM (stale category set, phantom savepoint, double-search+cap), 2 LOW (indexes, undeclared dep)**, plus a brittle seed-count test. Install + upgrade clean; **45/45 tests green** with 2 new regression tests.

---

## Original Issues Found

### Fixed

| # | Sev | Title | Root cause |
|---|-----|-------|-----------|
| H1 | HIGH (perf) | `resolve()` N+1 `search()` per SKU on the hot path | `southbrook_hardware_catalog.py:173-174` did one `Product.search([("x_marathon_sku","=",sku)],limit=1)` per SKU (~8-12/carcass). `resolve()` is called by BoM generation across whole orders → hundreds of round-trips. |
| M1 | MEDIUM (correctness) | Wizard **rejected valid** `end_panel`/`filler`/`corner_mech` rows | `HARDWARE_CATEGORY_KEYS` was a **stale hard-coded copy** of the model's `HARDWARE_CATEGORIES`, missing the 3 categories added 2026-06-18 (which the seeds actively use). Any CSV row using them failed validation — panels/corner-mechs could be seeded via XML but never imported. |
| M2 | MEDIUM (integrity) | CSV import claimed savepoint isolation it didn't have | The comment promised "per-row savepoint," but there was **no `savepoint()`** and the `except` caught only `(UserError, ValidationError, KeyError, ValueError)`. A DB `IntegrityError` at `create()` aborted the whole transaction and poisoned the cursor → every subsequent row also failed (a duplicate on row 140 discards rows 2-139). |
| M3 | MEDIUM (perf) | Double `search()` per row + unbounded read | Each row searched `x_marathon_sku` twice (caller pre-check + `_process_row`); the whole file was `list(reader)`'d with no row cap. |
| L1 | LOW (perf) | `x_hardware_brand_id` / `x_hardware_category` unindexed | The brand/category filter axes sequential-scanned `product_template`. |
| L2 | LOW (fragility) | Undeclared `stock` dependency | Module uses `is_storable` + `stock.menu_stock_root` but `stock` was present only transitively via `estimating→mrp→stock`. |
| T1 | (test) | Brittle `assertEqual(36 brands)` | Contradicted its own "growth is fine" docstring (and the sibling SKU floor-test); the seed legitimately grew to 39. |

### Documented (not applied)

| # | Sev | Title | Why not auto-fixed |
|---|-----|-------|--------------------|
| D1 | LOW | No `groups=` on `x_pricing_pending`/cost writes; no `pending_pricing` approval hook | Not exploitable today (`base.group_user` gets brand-**read** only; all catalog mutation is manager-gated); a pricing-approval workflow is a scope/policy decision. |
| D2 | LOW | No SQL unique constraint on `x_marathon_sku` | Adding `UNIQUE` could fail to install against existing prod data if duplicates exist; the savepoint fix already handles the resulting `IntegrityError` gracefully. Recommend a data-audit first. |
| D3 | LOW | Shipped `marathon_csv_template.csv` uses 3 brand codes not in the seed; registry-attr JSON cache is non-idiomatic; template-level SKU on variant-bearing templates is ambiguous | All labeled/latent, no live impact. |

---

## Repairs Completed
- **H1** — `resolve()` now does one `Product.search([("x_marathon_sku","in",list(totals))])` and a `setdefault`-built `{sku: product}` map (preserves the prior `limit=1`-picks-first semantics + the skip-and-warn on missing SKU).
- **M1** — `HARDWARE_CATEGORY_KEYS = {key for key,_ in HARDWARE_CATEGORIES}` (imported from the model — single source of truth, can't drift again).
- **M2** — wrapped each row in `with self.env.cr.savepoint():` and broadened the `except` to include `IntegrityError`; the savepoint rollback restores a usable cursor so the loop survives DB-level row errors.
- **M3** — `_process_row` now does the single existence search and returns `"created"/"updated"` (dropped the caller's duplicate search); added `MAX_IMPORT_ROWS = 20000` cap.
- **L1** — `index=True` on `x_hardware_brand_id` and `x_hardware_category`.
- **L2** — added `"stock"` to `depends`.
- **T1** — `assertEqual(36)` → `assertGreaterEqual(36)` (floor, matching the docstring + sibling test).

## Files Changed
`models/southbrook_hardware_catalog.py`, `models/product_template.py`, `wizards/southbrook_hardware_import.py`, `__manifest__.py`, `tests/test_csv_import.py` (+2 tests), `tests/test_seed_integrity.py`.

## Database Impact
- New indexes on `x_hardware_brand_id`/`x_hardware_category` (additive). No schema/migration; no constraint added (see D2).

## Security Improvements
- No new surface; the import row-cap (M3) adds a memory-DoS guard (manager-gated). Pricing-integrity hardening documented (D1).

## Performance Improvements
- `resolve()` hot path: N searches → **1** (H1). Import: 2 searches/row → **1** (M3). Brand/category indexed (L1).

## Remaining Risks
- **M2 residual**: an `IntegrityError` row is now skipped+logged rather than aborting the import; without a unique constraint (D2) the upsert's `limit=1` could pick one of several duplicate SKUs. Recommend a SKU-uniqueness data audit, then add the constraint.

## Recommendations (priority)
1. **D2** — audit `x_marathon_sku` for duplicates, then add a `models.Constraint` unique.
2. **D1** — add `groups=`/approval to pricing fields if pricing integrity is in scope.
3. **D3** — fix the shipped CSV template's brand codes; consider `ormcache` for the JSON map.
