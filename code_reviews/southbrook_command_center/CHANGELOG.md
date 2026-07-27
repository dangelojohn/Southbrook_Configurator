# CHANGELOG — southbrook_command_center

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #46 · APEX)

### Fixed — security
- **Company scoping (S1, HIGH).** `controllers/main.py` — `_validated_company_id`
  clamps the client-supplied `company_id` to `env.user.company_ids`; company domains
  added to `_flow`/`_recommendations`/`_alerts` (field-guarded). New global multi-company
  `ir.rule` on `southbrook.command.exception` (`security/command_center_groups.xml`).
- **Route group gate (S3, MED-HIGH).** `_require_cc_member` (internal + any of the 6
  command-center groups) on both `bootstrap` and `help_lookup` → `AccessError` for
  non-members (stops factory_health/flow leak + the exec-snapshot write from a read
  endpoint + training enumeration to portal).
- **Bus cleartext leak (S2, HIGH-latent).** `models/breakdown_alert.py` — dropped
  `impact_summary` from the alerts bus payload (guessable unauthenticated channel);
  the client re-fetches by `res_id` via the ACL-checked ORM.

### Fixed — v19 / frontend
- **Bus lifecycle events (V1).** `static/src/js/central_command.esm.js` —
  `connect/disconnect/reconnect` → `BUS:CONNECT/BUS:DISCONNECT/BUS:RECONNECT`.
- **`type="json"` → `type="jsonrpc"` (V2)** on both routes.

### Tests
- `tests/test_command_center.py` — new `TestCommandCenterAuth` (HttpCase): a non-member
  gets an error envelope from `/command_center/bootstrap`; a command-center member gets a
  `result` with `factory_health`.

### Not changed (documented in REVIEW_REPORT.md)
- Bus channel re-scoping to per-user record channels (Phase-3 websocket design); `role`
  is a presentation hint (derive server-side for role separation); exception owner-SoD
  `ir.rule` (role groups already read-only); `bottleneck_line_ids` sub-panel; dormant
  scoring methods.

### Manifest
- Version `19.0.1.1.1` → `19.0.2.0.0`.
