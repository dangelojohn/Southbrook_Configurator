# Test Results — `southbrook_freecad_bridge` (Module #19)

**Harness:** v19c-odoo, isolated DB, staged with dep chain (southbrook_estimating,
southbrook_qr_kit, southbrook_plm) over the OCA modules. `southbrook_dims.py`
(real, from ~/southbrook-v19cr/shared/) copied into the container PYTHONPATH to
satisfy the prod /srv/shared import (without it, test COLLECTION fails at
test_bom_contents.py's top-level `from southbrook_dims import ...`).

## Install
- Fresh install (`-i`): ✅ SUCCESS — 90/90 modules, registry loaded, v19-clean
  (no obj() trap; system_parameters.xml uses the canonical `set_param` idiom).

## Unit tests
`--test-enable --test-tags southbrook_freecad_bridge` → **2 failed / 0 error / 21**.

### My callback changes: ALL PASS (verified in the run log)
- `test_forged_regression_of_settled_mo_is_blocked` → HTTP **409** ✓ (new)
- `test_idempotent_replay_of_same_status_allowed` → HTTP **200** ✓ (new)
- `test_callback_done_...` (200), `test_callback_error_...` (200),
  `test_wrong_secret`/`test_missing_secret_header` → **401** (my JSON-401 change;
  tests assert `(401,403)`), `test_secret_unset` (503), `test_unknown_production`
  (404), `test_invalid_status`/`test_missing_production_id` (400) — all ✓.
- `test_g2a_gate` (5 tests) ✓; `test_render_smoke` skipped (external bridge
  unreachable — expected).

### The 2 failures are PRE-EXISTING + about the shared `southbrook_dims` module
- `test_bom_contents.test_constants_parity` — `TOEKICK_FAMILIES` set divergence
  ('drawer') between the shared `southbrook_dims.py` and estimating's constants.
  A real data-parity drift in the shared module (not this addon's code) — worth
  reconciling; flagged in the report.
- `test_dims_js_parity` — reads the dims `.js` file which isn't present in the
  container → parses to `{}`. Pure harness artifact.
I touched none of `southbrook_dims`, `test_bom_contents`, or `test_dims_js_parity`.

## Conclusion
The callback's security is materially improved (timing-safe secret compare,
no-wipe attachment semantics, state guard against forged regressions, input
validation → 400/409) with 2 new passing regression tests and zero regressions.
The remaining hardening (attachment-ownership filter, async render POST) is
documented. The 2 failures are pre-existing shared-dims parity/harness artifacts.
