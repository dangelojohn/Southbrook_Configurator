# Changelog — `product_configurator_mrp` (OCA, Southbrook-modified)

## 19.0.1.1.0 — 2026-07-10 (code review #7)

Excellent v19 port; two HIGH defects fixed. No v19-compat issues.

### Fixed
- **HIGH (data integrity):** `create_get_bom` common-BOM-line branch used the
  stale `values` instead of its own onchange result `values2`
  (`models/product_config.py`) → wrong `mrp.bom.line` data. Now `values=values2`.
- **HIGH (broken feature):** widened `access_product_configurator_mrp` from
  manager-only to `product_configurator.group_product_configurator` — the
  Configure/Reconfigure buttons (shown to all internal users) now open a wizard
  those users can actually access (was `AccessError`).
- **LOW:** removed the dead `"qweb"` manifest key (unprocessed in v19).

### Verified clean (no change)
All 13 v19 axes; no `sudo`/`cr.execute`/`eval`-on-user-input. The diverged
`static/src/xml/mrp_production_views.xml` is a correct v19 port fix (drops the
stale `[2]` create-button-slot xpath index). `column_invisible="parent.…"`
verified correct against core mrp.

### Documented (not changed)
Dead `group_product_configurator_mrp`; N+1 `operation_ids.copy()`; hoist
`get_onchange_specifications` out of the BOM loop; BoM-duplication TOCTOU (use an
advisory lock — NOT a unique constraint, core mrp.bom allows multiple BOMs/product).
See `REVIEW_REPORT.md`.
