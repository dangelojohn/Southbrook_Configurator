# Changelog — `southbrook_mrp_kitchen_tools`

## 19.0.1.0.0 — 2026-07-11 (code-review pass, module #30)

### v19 correctness — Fixed
- **V1 (CRITICAL runtime)** — `mrp.workorder.button_start` now accepts and
  forwards `raise_on_invalid_state` (v19's base signature; the standard UI "Start"
  action passes `raise_on_invalid_state=True`). The old `def button_start(self)`
  raised `TypeError` on every UI Start.
- **V2** — removed the dead v19 `name_get` override on `southbrook.tool.category`
  (`display_name` already derives from `_rec_name = "complete_name"`).

### Security / integrity — Fixed
- **H1 (HIGH)** — QR tool checkout (`qr_kind_handlers.py`) now rejects a checkout
  when an open usage row already exists (no more double-checkout of one physical
  tool), and sets the asset `lifecycle_state = "checked_out"` + `current_holder_id`
  on checkout (cleared on check-in) so the readiness gate stops counting an issued
  tool as available.
- **H2 (HIGH)** — checkout sets `checked_out_by` to the real acting user instead of
  the OdooBot that the `sudo()` create defaulted to (fixes the audit trail).
- **H3 (HIGH)** — `southbrook.workorder.tool.consumption`: added
  `@api.constrains` rejecting negative `quantity`/`unit_cost` (a negative quantity
  silently *un-wore* tools via `_apply_to_asset_life` and deflated the MO cost
  rollup); `create` now sources `unit_cost` from the product's `standard_price`
  when the caller supplies none.
- **M2 (MEDIUM)** — the work-order readiness category match uses `child_of` instead
  of one-level `child_ids`, so assets under a grandchild category are counted (no
  more false "blocked" refusing to start a WO).

### Tests (+7 regression)
- `test_qr_checkout_marks_asset_checked_out_and_attributes_operator`,
  `test_qr_double_checkout_is_rejected`, `test_qr_checkin_returns_asset_to_available`
  (H1/H2); `test_negative_quantity_rejected`, `test_negative_unit_cost_rejected`
  (H3); `test_button_start_accepts_v19_raise_on_invalid_state_kwarg` (V1);
  `test_readiness_counts_grandchild_category_asset` (M2).

### Not changed (documented in REVIEW_REPORT.md)
- M1 lifecycle_state state-machine guard, M3 company_id/record rules (multi-company
  policy), L1 readiness N×R query batching, L2 "New" sequence-fallback collision.
