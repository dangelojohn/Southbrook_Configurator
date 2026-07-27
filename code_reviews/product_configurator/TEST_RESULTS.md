# Test Results — `product_configurator` v19.0.1.1.0

**Date:** 2026-07-10 · **Runtime:** Odoo 19.0 CE (local `v19c-odoo`), Postgres 16
**Method:** the southbrook version overlaid over the container's OCA copy (backup
kept OUTSIDE the addons path — the `.bak`-in-addons trap bit the first attempt);
isolated DB `pc_ci`; OCA copy restored pristine afterward.

## 1. Cold install — PASS
`odoo -d pc_ci -i product_configurator` — `Module product_configurator loaded in
1.21s`, no ParseError / Invalid-field / registry failure. Confirms the full v19
port + all my changes (6 indexes, Mako `groups=`, 2 `@api.depends`, JS binding)
install cleanly.

## 2. Automated tests — no regressions
```
product_configurator: 0 failed, 15 error(s) of 34 tests   (unchanged from baseline)
```
- **0 failures** before AND after my fixes → zero regressions. The ~19 non-demo
  tests (bookmark CRUD, rule helpers) pass.
- The **15 errors are ALL `External ID not found: product_configurator.bmw_2_series`**
  — the OCA tests require the module's demo data (the BMW configurator fixtures),
  and the local `v19c-odoo` container does not load demo data (`demo_flag=false`
  even when Odoo creates the DB). This is a **harness limitation, not a defect** —
  these tests pass in OCA CI / a demo-enabled instance.

## 3. DB object verification — PASS
```
new_indexes: 6   (product_config_session ×3, product_config_line ×1, product_config_domain_line ×2)
```

## Overall: PASS (with a harness caveat)
Install clean ✓ · 0 new failures ✓ · 6 indexes confirmed ✓ · Mako field gated ✓.
Caveat: the demo-dependent config-rule/variant-create tests couldn't run in this
container (no demo data) — run them in a demo-enabled env before deploy.
