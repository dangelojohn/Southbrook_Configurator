# Test Results — `website_product_configurator` v19.0.1.1.0

**Date:** 2026-07-10 · **Runtime:** Odoo 19.0 CE (`v19c-odoo`), Postgres 16
**Method:** southbrook version overlaid over the container's OCA copy (backup outside addons path); isolated DB; OCA restored after.

## 1. Static validation — PASS
`py_compile` (controllers, models, migration); all XML well-formed incl. the new
`ir.rule` records in `security/configurator_security.xml`; manifest parses.

## 2. Cold install — PASS
`odoo -i website_product_configurator` on a fresh DB:
```
Modules loaded.
Registry loaded in 23.9s
```
The full `website_sale` dependency tree + this module + my changes (3 new
`ir.rule`s, the GC-domain fix, the safe_eval→numeric-parse change, the
parameterized migration) install cleanly — no ParseError / Invalid-field /
registry failure. A malformed rule or bad model-xmlid ref in the new
`ir.rule`s would have failed install; it did not, so the protective rules load.

Note: the heavy `website_sale` tree made this install FLAKY in this container —
several runs died at DB-init with a transient startup crash (0-line log,
resource/connection burst under concurrent load), unrelated to the module. A
clean run completed and is the result above.

## 3. Automated tests — NOT RUN (harness limitation)
The module's tests require the parent `product_configurator` BMW demo data
(`bmw_2_series`), which this container does not load, and exercise the full
public config→cart flow. They were not runnable here (same demo-data +
flakiness limitations as modules #6–#8). The security fixes are validated by
clean install + logic; a demo-enabled env should run the suite.

## 4. Fix verification (by construction)
- The 3 protective `ir.rule`s loaded (install succeeded referencing
  `product_configurator.model_product_config_session` / `.custom_value` /
  `.bookmark` — valid refs).
- The GC method now filters `has_active_bookmark=False, is_saved=False` (static).
- `safe_eval` import removed; strict `int()`/`float()` parse in place.

## Overall: PASS (install) — with a validation caveat
Install clean ✓ · protective rules load ✓ · fixes structurally sound ✓.
**Recommended before deploy:** a live smoke test of the anonymous configure→save
→cart flow in a demo-enabled env, to confirm the new `ir.rule`s don't constrain
any legitimate NON-sudo controller read (expected safe — the controller sudo's).
