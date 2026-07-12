# CHANGELOG — southbrook_integrations

## 19.0.2.0.0 — 2026-07-11 (code-review campaign, module #41)

### Fixed — security (MCP surface)
- **Sudo read → ACL bypass (C1, CRITICAL).** `models/mcp_tool.py` `invoke()` no
  longer reads under `.sudo()` — the `search`+`read` runs as the invoking
  principal so record rules / ACL / company scoping apply.
- **Internal-only MCP (C1).** `controllers/mcp_api.py` `requires_mcp_auth` now
  rejects non-internal users (`user._is_internal()` → 403), so portal-customer
  API keys can't reach the endpoint.
- **Sensitive-model blocklist (H1).** `models/mcp_tool.py` — an `@api.constrains`
  blocks tools targeting `ir.config_parameter`, `ir.mail_server`, `res.users`,
  `res.users.apikeys`, `southbrook.api.key`, `ir.model.data`.
- **Removed caller `extra_domain` (M1).** Wire-supplied domains are no longer
  accepted; the tool's `domain_json` is the only scope.
- **Paging clamp + rate-limit enforcement (M2).** `limit` clamped to `[1,500]`,
  `offset ≥ 0`; the controller returns **429** when the per-minute budget is hit.
- **Audit principal (M3).** `models/mcp_call_log.py` gained a `user_id`; every
  `invoke()` log-create records the authenticated principal.

### Fixed — functional
- **Seed MCP tools now load (F-DATA, HIGH).** `__manifest__.py` — added the
  omitted `data/mcp_tools.xml`; the 4 seed tools are created (the `/invoke`
  endpoint had 404'd for every documented tool).
- **mi_tiles seed + ACL (TILE, F3).** `security/ir.model.access.csv` grants
  manager create/unlink; new `data/mi_tiles.xml` seeds the Integrations Snapshot
  singleton.

### Tests
- `tests/test_asn_3pl.py` — dropped the removed `stock.move.name` key from the
  move command dicts (fixes the baseline `KeyError` that blocked the class).
- `tests/test_mcp_tool.py` — +2 regression tests: `test_sensitive_model_is_blocked`
  (H1), `test_invoke_records_principal` (M3).

### Not changed (documented in REVIEW_REPORT.md)
- L1 `southbrook.api.key.verify()` active-check (lives in southbrook_api #28);
  L2 CORS `*`; L3 IoT ZPL `_resolve` getattr repr leak.

### Manifest
- `data/mcp_tools.xml` + `data/mi_tiles.xml` added; version `19.0.1.0.0` → `19.0.2.0.0`.
