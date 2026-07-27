# CHANGELOG — southbrook_floor_traveler

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #44)

### Fixed — security
- **Scan-endpoint IDOR / portal reachability (C1/H1, CRITICAL).**
  `controllers/scan_endpoint.py` — `floor_traveler_scan` now requires an internal
  `mrp.group_mrp_user` caller (`_is_internal()` + `has_group`) → `forbidden` else,
  before any work. Previously any authenticated user (incl. a portal customer) could
  advance/finish any workorder via a guessed `sb-package:<id>` (sudo-advanced, no
  object/group check).
- **Scan-log attribution (M1, MED).** The sudo log create now records the real caller
  (`user_id: env.uid`) — was OdooBot on a production-mutation audit log.
- **type future-proofing.** `type="json"` → `type="jsonrpc"` (v19 alias; silences the
  deprecation + survives a v20 removal).

### Tests
- `tests/test_p8_floor_traveler.py` — bypass the premium_orchestration MO availability
  gate in the setUp helper; isolate the tool-consumption test to a FRESH tool category
  (the seeded `cat_blade_melamine` ships asset(1), which the category-based resolver
  picked over the test's asset — same seed-collision class as module 43).
- New `TestP8ScanEndpointAuth.test_non_mrp_user_is_forbidden` (HttpCase) — a plain
  internal user gets `forbidden` from the scan endpoint.

### Not changed (documented in REVIEW_REPORT.md)
- C2 `record_scan` sudo (kept — group-authorized shop-floor model + legit cross-model
  write; the gate is the boundary); C3 replay/idempotency (needs nonce/TTL with qr_kit);
  retire the unsigned `sb-package:<id>` format (requires re-issuing printed travelers);
  LOW1 scan-log read scope.

### Manifest
- Version `19.0.1.2.1` → `19.0.2.0.0`.
