# TEST_RESULTS — southbrook_cmms_wms

**DB:** `ci_cmms40` (isolated, full southbrook MI + kitchen_tools dep stack)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Baseline (HEAD, before fixes)
`-i` + `--test-tags=/southbrook_cmms_wms`: install clean (~72 s), **1 error of 7**.
- `test_landed_cost_template_apply_creates_landed_cost` **ERROR** — `KeyError: 'name'`
  during `stock.picking.create`: the move command dict `{"name": …}` references
  `stock.move.name`, **removed in v19**. (The oversize test used the same dict but
  skipped earlier on the missing product-dimension field, hiding the same bug.)

## After fixes (19.0.2.0.0)
```
southbrook_cmms_wms: 8 post-tests
0 failed, 0 error(s) of 8 tests when loading database 'ci_cmms40'
```

| Phase | Result |
|-------|--------|
| `-i southbrook_cmms_wms` (fresh DB, incl. 2 crons, sequences, mi_tiles seed) | **clean**, registry ~67 s |
| `-u southbrook_cmms_wms` | **clean**, 2.2 s |
| `--test-tags=/southbrook_cmms_wms` (8 post-tests) | **8 pass / 0 fail / 0 error** |
| mi_tiles probe (`odoo shell`) | `mi_tiles_default` materialized; tiles compute live — no crash |

## New / repaired tests
- `test_expiry_cron_runs_and_deduplicates` (NEW) — the previously-untested expiry
  cron runs without the `res.groups.users` crash, posts an alert, stamps
  `last_alert_date`, and a same-week second run is throttled (no re-alert).
- Move command dicts fixed (removed `stock.move.name`); the landed-cost test now
  reaches `apply_to_picking` and **skips by design** on the bare-DB landed-cost
  setup gap ("null value in column product_id of stock_landed_cost_lines") — its
  own `except UserError: skipTest` fallback.

## Field-existence probes
- `stock.move.name` → **absent** in v19 (root cause of the baseline error).
- `stock.move` valid keys confirmed: `product_id, product_uom_qty, product_uom,
  location_id, location_dest_id, description_picking`.
- `res.groups` → `user_ids` / `all_user_ids` (no `users`) — root cause of V1.

## Documented gaps surfaced by tests
- Landed-cost `apply_to_picking` creates a cost line with no `product_id` → NOT-NULL
  violation on `stock_landed_cost_lines` in a bare DB (needs a configured
  landed-cost service product). The test skips; documented as L11.

## Notes
- Pre-existing core-website `@class`/RST warnings + `sms` "Unavailable during module
  installation" during `-i` are unrelated (other modules / core demo), non-fatal.
