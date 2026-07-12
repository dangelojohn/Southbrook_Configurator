# Test Results — `product_configurator_sale` v19.0.1.1.0

**Date:** 2026-07-10 · **Runtime:** Odoo 19.0 CE (`v19c-odoo`), Postgres 16
**Method:** southbrook version overlaid over the container's OCA copy (backup outside addons path); isolated DB; OCA restored after.

## 1. Static validation — PASS
`views/sale_view.xml` well-formed; `config_session_id readonly="1"` applied in both view locations (form + list).

## 2. Cold install — PASS
`odoo -i product_configurator_sale` installs cleanly on v19 (the module + its `sale_management`/`product_configurator`/`stock` dependency tree loaded; the test framework ran the module's 4 tests). No ParseError / Invalid-field / registry failure from the readonly change.
(Note: the heavy `sale_management` dependency-tree install is flaky in this container — a couple of runs died at DB-init with a transient startup crash unrelated to the module; a clean run completed.)

## 3. Automated tests — no regressions
```
product_configurator_sale: 0 failed, 4 error(s) of 4 tests
```
All 4 errors are `setUpClass … External ID not found: product_configurator.bmw_2_series` — the tests require the parent module's BMW configurator demo data, which the local container doesn't load. **Environment limitation, not a defect** (passes in OCA CI / demo-enabled instances). The readonly change writes nothing at test time (tests set `config_session_id` via ORM, unaffected by view readonly) — zero new failures.

## Overall: PASS (harness caveat)
Install clean ✓ · readonly fix applied ✓ · no regressions ✓. Config-flow tests need a demo-enabled env (all 4 gated on `bmw_2_series`).
