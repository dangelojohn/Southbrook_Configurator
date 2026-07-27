# CHANGELOG — southbrook_mes_mps

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #39)

### Fixed — v19 / runtime crashes
- **Bottleneck cron crash (V1, HIGH).** `models/bottleneck_report.py` —
  `sup_group.users` → `sup_group.user_ids` (v19 renamed `res.groups.users`). The
  daily cron `AttributeError`'d every run once a top bottleneck existed.
- **MPS pivot crash (V2, HIGH).** `views/mps_period_views.xml` — removed the
  non-stored `to_supply_qty` pivot measure (`_read_group` can't aggregate a
  non-stored compute); it stays a summed list column.

### Fixed — computation / display
- **OEE cron always 0 (O1, HIGH).** `models/oee_snapshot.py`
  `action_compute_from_workcenter_productivity` now derives `units_produced` /
  `units_target` from the workorders referenced by the day's productivity rows
  (`qty_produced` / `qty_production`) instead of hardcoding 0 (which forced every
  snapshot to OEE 0% / "unacceptable" and poisoned the 7-day average).
- **Percentage widget 100× (PCT, HIGH).** Removed `widget="percentage"` from the
  five `*_pct` view fields (they already store 0–100). Kept it on the OEE
  fraction fields (0–1). A 150%-loaded WC had shown "15000%".
- **Bottleneck fallback state filter (B2, MED).** `models/bottleneck_report.py` —
  the inline (no-capacity-row) branch now filters workorders to
  `('blocked','ready','progress')`, matching the capacity model (was summing
  done/cancelled too).

### Fixed — dead feature
- **MES Snapshot seed (TILE).** New `data/mi_tiles.xml` seeds one `noupdate`
  `MES/MPS Snapshot` record (the menu / MI dashboard was empty without it).

### Tests
- `tests/test_bottleneck_identifies_top.py` — rewrote the fixture to stage real
  workorders (10h/30h/60h) so `capacity.planned_hours` (a computed field, not
  seedable) reflects the intended 25/75/150% loads. The bottleneck ranking logic
  was already correct.

### Not changed (documented in REVIEW_REPORT.md — algorithmic / policy)
- M1 no projected-on-hand roll-forward (net requirements wrong for weeks ≥2 — a
  core MPS-semantics redesign); B1 header-vs-line ranking metric; C1 cron per-row
  try/except; demand-by-date_order; `mi_tiles` perm_write for users; dead
  `search_default_group_by_product`.

### Manifest
- `data/mi_tiles.xml` added; version `19.0.1.0.1` → `19.0.2.0.0`.
