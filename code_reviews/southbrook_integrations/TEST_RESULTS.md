# TEST_RESULTS — southbrook_integrations

**DB:** `ci_int41` (isolated, full api/quality/payroll/finance/MI/kitchen dep stack)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Baseline (HEAD, before fixes)
`-i` + `--test-tags=/southbrook_integrations`: install clean (~66 s), **1 error of 11**.
- `setUpClass (test_asn_3pl.TestAsn3pl)` **ERROR** — `ValueError: Invalid field 'name'
  on model 'stock.move'`: the move command dict `{"name": …}` references
  `stock.move.name`, **removed in v19**. The error blocked the whole `TestAsn3pl` class
  (so its tests never ran — the visible suite was smaller than reality).

## After fixes (19.0.2.0.0)
```
southbrook_integrations: 15 tests
0 failed, 0 error(s) of 15 tests when loading database 'ci_int41'
```

| Phase | Result |
|-------|--------|
| `-i southbrook_integrations` (fresh DB, incl. mcp_tools + mi_tiles seeds) | **clean**, registry ~66 s |
| `-u southbrook_integrations` | **clean**, 2.2 s |
| `--test-tags=/southbrook_integrations` (15 post-tests) | **15 pass / 0 fail / 0 error** |
| Seed probe (`odoo shell`) | 4 MCP tools created (was 0); `mi_tiles_default` materialized |

## New regression tests
- `test_sensitive_model_is_blocked` — defining a tool on `ir.config_parameter`
  raises `UserError` (H1).
- `test_invoke_records_principal` — the call log's `user_id` equals the invoking
  user (M3).

## Notes
- The `test_asn_3pl` fix restored 2 previously-blocked tests (11 → 13 pre-regression,
  15 with the 2 new tests).
- The MCP tools now run under the invoking principal (no sudo); the seed business
  tools (payroll/finance/NCR) therefore require the MCP service account to hold the
  relevant read groups — the intended, ACL-bounded model.
- Pre-existing core-website `@class`/RST warnings during `-i` are unrelated, non-fatal.
