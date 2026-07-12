# CHANGELOG — `southbrook_hardware_catalog`

## 19.0.2.2.0 — 2026-07-11 — Code-review pass (Module #14)

### Performance
- **[HIGH] `resolve()` batches the SKU→product lookup.** One
  `Product.search([("x_marathon_sku","in",…)])` + a dict replaces the per-SKU
  `search()` loop on the per-carcass BoM hot path. `models/southbrook_hardware_catalog.py`.
- **[MEDIUM] CSV import: one existence search per row** (was two — caller +
  `_process_row`); `_process_row` returns `"created"/"updated"`.
  `wizards/southbrook_hardware_import.py`.
- **[LOW] Indexed `x_hardware_brand_id` and `x_hardware_category`.**
  `models/product_template.py`.

### Fixed
- **[MEDIUM] Wizard no longer rejects valid `end_panel`/`filler`/`corner_mech`
  rows.** `HARDWARE_CATEGORY_KEYS` now derives from the model's
  `HARDWARE_CATEGORIES` (was a stale hard-coded copy). `wizards/…import.py`.
- **[MEDIUM] CSV import per-row isolation is now real.** Each row runs in a
  `cr.savepoint()` and the `except` includes `IntegrityError`, so a DB-level
  error on one row no longer aborts the whole import / poisons the cursor.
  Added a `MAX_IMPORT_ROWS` cap. `wizards/…import.py`.
- **[LOW] Declared `stock` explicitly** in `depends` (was transitive-only).
  `__manifest__.py`.

### Tests
- Added `test_import_accepts_extended_categories` (end_panel/corner_mech/filler)
  and `test_bad_row_does_not_discard_good_rows` (per-row isolation).
- Fixed brittle `test_all_36_brands_present`: `assertEqual(36)` →
  `assertGreaterEqual(36)` (floor), matching its own docstring and the sibling
  SKU test; the seed legitimately grew to 39. `tests/test_seed_integrity.py`.
- Result: **45/45 green** (install + upgrade).

### Notes (documented, not changed)
- No `groups=`/approval on pricing fields (not exploitable — base users get
  brand-read only) — D1.
- No SQL unique constraint on `x_marathon_sku` (would risk install failure on
  existing duplicate data; audit first) — D2.
- Shipped CSV template brand codes / registry-attr JSON cache / variant-SKU
  ambiguity — latent, no live impact — D3.
