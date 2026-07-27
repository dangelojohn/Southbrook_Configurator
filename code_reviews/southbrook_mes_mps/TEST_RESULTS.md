# TEST_RESULTS — southbrook_mes_mps

**DB:** `ci_mes39` (isolated, full southbrook MI + kitchen_mrp + workcenters dep stack)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Baseline (HEAD, before fixes)
`-i` + `--test-tags=/southbrook_mes_mps`: install clean (~88 s), **1 failed of 8**.
- `test_bottleneck_identifies_top.test_top_bottleneck_is_highest_load` **FAIL** —
  `mrp.workcenter(26) != mrp.workcenter(28)`: the fixture seeded `capacity.planned_hours`
  (a computed field from `mrp.workorder`), which was overwritten to 0 → all three lines'
  `load_pct` read 0 → `max` returned the first (low) instead of the intended high-load WC.

## After fixes (19.0.2.0.0)
```
southbrook_mes_mps: 16 tests
0 failed, 0 error(s) of 8 tests when loading database 'ci_mes39'
```

| Phase | Result |
|-------|--------|
| `-i southbrook_mes_mps` (fresh DB, incl. crons, sequences, mi_tiles seed) | **clean**, registry ~66 s |
| `-u southbrook_mes_mps` | **clean**, 2.4 s |
| `--test-tags=/southbrook_mes_mps` (16 tests) | **16 pass / 0 fail / 0 error** |
| mi_tiles probe (`odoo shell`) | `mi_tiles_default` materialized; tiles compute live — no crash |

## Repaired test
- `test_top_bottleneck_is_highest_load` — fixture now stages real workorders
  (10h/30h/60h → 25%/75%/150% load); asserts HighWC is top, `load_pct > 100`,
  `recommended_action == "add_shift"`.

## Field-existence probes
- `mrp.workcenter.productivity` fields: `production_id, workorder_id, loss_id, duration`
  (no per-row units → O1 derives units from the linked workorders).
- `mrp.workorder` fields: `qty_produced, qty_production, qty_producing, qty_remaining`
  (all present → O1 unit derivation valid).

## Existing coverage
`test_oee_computation` (world-class / unacceptable / zero-division-safe — exercises the
correct `_compute_oee`), `test_mps_rolling_13_weeks` (13 rows, idempotent),
`test_workcenter_load_compute` (load from workorders, zero when none).

## Notes
- Pre-existing core-website `@class`/RST warnings + `sms` "Unavailable during module
  installation" during `-i` are unrelated (other modules / core demo), non-fatal.
- O1's cron unit-derivation isn't covered by a dedicated regression test (would need a
  `mrp.workcenter.productivity` + workorder fixture) — noted as a follow-up; the
  underlying `_compute_oee` is already tested.
