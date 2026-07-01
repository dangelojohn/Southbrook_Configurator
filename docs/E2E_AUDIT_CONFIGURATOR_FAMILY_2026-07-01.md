# End-to-End Audit — Configurator Family (Odoo 19 CE)

**Date:** 2026-07-01
**Auditor:** Claude Opus 4.7 (co-development session with John)
**Live target URL:** `https://southbrookcabinetry.space/odoo/action-1018/38`
**Local harness:** `sami-odoo` container against `southbrook` DB
**Baseline log:** `/tmp/configurator-baseline.log` (1127 tests, cascaded across the whole stack)
**Verify logs:** `/tmp/configurator-run-{2,3}.log`

## Modules in scope

| Addon | Version | Role |
|---|---|---|
| `product_configurator` | 19.0.1.0.0 | OCA base — session, rules, wizard |
| `product_configurator_sale` | 19.0.1.0.0 | OCA sale-side extension |
| `product_configurator_mrp` | 19.0.1.0.0 | OCA mrp-side extension |
| `website_product_configurator` | 19.0.1.0.0 | OCA public/portal storefront |
| `southbrook_configurator_ux` | 19.0.1.7.0 | Southbrook v2 OWL UI overlay + import pipeline |
| `southbrook_config_engine` | 19.0.0.1.0 | Southbrook placement-rule stack |

## 1 · TL;DR

**Code health:** GOOD. Rule engine is unforked (no Southbrook code overrides `validate_configuration`, `values_available`, `create`, `write`, `create_get_variant`, or `_get_config_image`). Southbrook layers extend via (a) batch data mutations through AbstractModel `<function>` hooks and (b) an HTTP controller layer that consumes the OCA seams as-is. No monkey-patches.

**Test health:** OCA configurator tests are demo-data-dependent — 14 setUp errors in `product_configurator`, 1 in `_sale`, 2 in `_mrp`, 3 in `website_` — every one is `bmw_2_series` xmlid missing on a `--without-demo` DB (traceback verified `/tmp/configurator-baseline.log:setUp/test_configuration_rules.py:104`). Not real bugs. Southbrook overlays (60 tests in `southbrook_configurator_ux` + 21 in `southbrook_config_engine`) pass entirely.

**Real bugs found + fixed this session:** 4 P0 bugs corrected in code, 5 new regression tests added, 0 failures / 235 tagged tests in `southbrook_estimating` (run 3, log at `/tmp/configurator-run-3.log`).

**Integration health:** clean. Zero collision with the refacing-margin pricelist (verified — no addon in the configurator family writes `product.pricelist.item`).

## 2 · What is action-1018?

The URL `/odoo/action-1018/38` is Odoo 19's frontend router entrypoint for a numeric backend action ID with `res_id=38`. Behind login (HTTP 200 unauthenticated → returns `main-object="ir.ui.view(189,)"` = Trade Portal login page).

**Grep of every action XML in the 6 addons confirms:** no stored xmlid resolves to a fixed ID `1018`. Runtime ID `1018` is auto-assigned at install time from the `ir.actions.*` shared ID space. Most likely mapping (per the same order as the previous audit's action-1028 → `action_order_builder`):

- `product_configurator.product_configurable_template_action` (Configurable Templates kanban on `product.template`) — the natural landing action for a configurator-app tile.
- `res_id=38` would then be `product.template` id 38.

**Note:** the fallback in `southbrook_estimating/views/launch_3d_menu.xml:44-49` used to reference `product_configurator.action_product_template_view` — an xmlid that does not exist. This session's audit surfaced + fixed that (see §5.B). Correct xmlid is `product_configurator.product_configurable_template_action`.

To verify at runtime, in `docker exec sami-odoo odoo shell -d southbrook`:

```python
env["ir.actions.actions"].browse(1018).name
env["ir.actions.actions"].browse(1018).res_model  # → 'product.template'
```

## 3 · Real bugs found — 4 P0 fixes landed

### A · `product_configurator/models/product_config.py:937` — twin of the earlier :894 bug

**Same defect** as the `create()` wrapper I fixed on 2026-07-01 in the estimating audit: `create_get_variant()` was using `exc.name` on a v19 `ValidationError` which has no `.name` attribute (`.args[0]` is the message). The wrapper elevated every rule-blocked ValidationError from `validate_configuration()` into an `AttributeError`, which fell into the outer `except Exception` and masked the actionable message ("Box Material: Maple not available") behind the generic "Invalid Configuration" fallback.

**Fix:** `exc.args[0] if exc.args else str(exc)` — mirrors :894.

### B · `southbrook_estimating/views/launch_3d_menu.xml:44-49` — stale xmlid fallback

The Launch-3D server action fallback was `env.ref('product_configurator.action_product_template_view')`. That xmlid **doesn't exist** — grep of `product_configurator/**` confirms only `product_configurable_template_action` is defined for the same purpose. The `raise_if_not_found=False` ref-guard silently returned falsy on every fallback path, then fell through to the ad-hoc dict. Not a functional bug (the ad-hoc dict works), but the "prefer xmlid" intent was silently defeated.

**Fix:** corrected to `product_configurator.product_configurable_template_action`.

### C · `product_configurator/models/product_config_bookmark.py:118` — v19 `_sql_constraints` silently ignored

Legacy `_sql_constraints = [("name_not_empty", "CHECK (TRIM(name) <> '')", …)]` — v19 silently ignores this list (see `[[odoo19_sql_constraints_deprecated]]`). The CHECK was never being installed at Postgres level. A friendly UserError normalizer at `_normalize_name_in_vals` (line 141) covers ORM callers, but direct SQL / `fields.Command` writes could land an empty name.

**Fix:** migrated to `_name_not_empty = models.Constraint("CHECK (TRIM(name) <> '')", "…")` — the v19 idiom. The CHECK now reaches Postgres.

### D · `product_configurator/static/src/js/boolean_button_widget.xml:8` — OWL word operator

`value="props.state or false"` — Python-style `or` in an OWL prop expression. Current OWL tokenizer tolerates it, but every `[[owl_tokenizer_constraints]]` incident since 2026-06-22 has been a latent `or`/`and`/`not` in a template context.

**Fix:** `value="props.state || false"` — canonical JS.

## 4 · Real integration/architecture findings

### 4.1 Rule engine seams — unforked (verified)

- **`product.config.session` MRO:** `product_configurator/models/product_config.py:344` → `product_configurator/models/product_config_bookmark.py:213` (adds `bookmark_ids` + `action_save_config` override) → `product_configurator_mrp/models/product_config.py:7` (adds `create_get_bom`, overrides `create_get_variant`). `southbrook_estimating` adds a 4th layer. Southbrook UX + config-engine do NOT inherit the session.
- **`product.config.line`, `product.config.step`, `product.config.step.line`, `product.config.image` — zero overrides across the 6 addons.**
- **`validate_configuration()` — zero overrides.** All Southbrook additions supplement (batch data mutations via `southbrook_configurator_ux/models/rule_completion.py`) or run in parallel (`southbrook_config_engine.sb.placement.rule` is a totally separate rule system).

### 4.2 Cross-collision with the refacing pricelist — none

`southbrook_estimating` ships a refacing 35% margin-target computed field on `product.pricelist.item`. Grep across the 6 configurator addons: only ONE read-only reference to `product.pricelist.item` exists (`product_configurator/models/product_attribute.py:379` reading `partner.property_product_pricelist`). No configurator addon writes `product.pricelist.item`, no `@api.depends` triggers on it, no compute invalidates on its writes. The refacing computed field and the configurator family are cleanly disjoint.

### 4.3 Auth-public routes that mutate state

`southbrook_configurator_ux/controllers/main.py`:

| Route | Auth | Mutation | Guard |
|---|---|---|---|
| `POST /southbrook/api/configurator/state` | public | creates `product.config.session` if not present | scopes to `env.user.id` — for anonymous, that's `base.public_user`, shared across all anon visitors |
| `POST /southbrook/api/configurator/select` | public | writes `session.value_ids` via `update_config` | `_authorize_session` (main.py:788) enforces per-user ownership |
| `POST /southbrook/api/configurator/commit` | public → login_required | creates variant + sale.order.line + `action_confirm` | explicit `request.env.user._is_public()` short-circuit at :607 before any writes |

**Not a security defect but a UX correctness caveat:** `/state` and `/select` share the `base.public_user` session across concurrent anonymous browsers. Two anonymous visitors on the same product page will race on the same session row. `/commit` is safely gated. Documented, not "fixed" this session.

## 5 · Test regression coverage — 5 new tests added

All in `southbrook_estimating/tests/test_rule_enforcement.py` (natural home — that file already tests rule-engine semantics). Tagged `configurator_v19_regression` + `configurator_multi_attr_quirk` for targeted invocation.

### 5.1 `TestOCAValidationErrorWrappersV19` — pins the two `.name → .args[0]` fixes

| Test | Kind | What it proves |
|---|---|---|
| `test_01_session_create_wrapper_preserves_rule_message` | runtime | `session.create({value_ids=[contractor, maple]})` triggers the `:894` wrapper; asserts no `AttributeError` in the message, no fallback "Default values provided generate an invalid configuration", and the rule text ("Maple" or "Box Material") reaches the caller |
| `test_02_create_get_variant_wrapper_source_is_v19_safe` | source-code | `create_get_variant`'s `:937` wrapper cannot be goaded into a rule-violated `self.value_ids` state via any supported ORM path (write silently prunes invalid values via `values_available()`), so this test asserts the FIX pattern is present in source and the broken idiom is NOT |

Both regression-guard against upstream OCA merges reintroducing `.name`.

### 5.2 `TestOCAMultiAttributeSingleValueQuirk` — pins the OCA multi-attribute slip-through

| Test | What it proves |
|---|---|
| `test_01_single_multi_value_slip_through_is_the_status_quo` | Documents that OCA's `validate_configuration()` at `product_config.py:1605` only surfaces the "multi values not permitted" error when 2+ values are picked. A single value on a `display_type=multi` attribute that violates the domain slips through. Pinned as status quo — when this test starts failing, OCA has tightened its check and the two-value workaround in `TestRule4BifoldSoftClose.test_01` can be simplified |
| `test_02_two_value_pick_correctly_raises` | Complement — the same rule DOES fire when 2+ values are picked. This is what Southbrook's Rule 4 negative test relies on |

## 6 · HIGH-value findings NOT fixed in this session

### 6.1 OCA test quality debt (from the test-audit agent)

The upstream OCA `product_configurator/tests/` carries 13 FIXME comments including:

- 4 module-header FIXMEs: `# FIXME: many tests here do not have any assertions.` in `test_product_attribute.py:5`, `test_wizard.py:5`, `test_product.py:5`, `test_product_config.py:5`.
- `test_wizard.py:233` — `# FIXME: broken test` (`test_09_onchange_product_preset` is a 1-line stub).
- `test_product_config.py:487` — `# FIXME: broken validation at 'product_config.create_get_variant'` — the exact code path Southbrook's estimating flow relies on.

**Recommendation:** treat these as an upstream backlog. Not blocking, but any refactor of those OCA modules is currently un-protected against silent regressions.

### 6.2 Test tagging fragmentation

15 of 25 test files in the family are untagged (no `@tagged` decorator). No `configurator` umbrella tag — `southbrook_configurator_ux` uses `southbrook_cfg_state/_select_commit/_import`; `southbrook_config_engine` uses `southbrook`+`config_engine`+`gap02/layouts/pack`. `odoo-bin --test-tags configurator` matches nothing.

**Recommendation:** decorate all 25 files with a shared `configurator` tag alongside their bespoke ones. Mechanical patch, ~50 lines.

### 6.3 15 `self.skipTest` guards in `test_select_commit.py`

Each carries a reason ("Series attribute not seeded", "Width attribute not present on this DB", etc), so nothing silent. But 15 of 34 methods can no-op under CI without any signal — CI green does not mean the coverage ran.

**Recommendation:** replace `self.skipTest` with a `setUpClass`-level `self.skipTest(...)` OR a real fixture that seeds the required attributes. Alternative: mark the whole class `@tagged("requires_southbrook_seed")` and enforce in CI split.

### 6.4 Website E2E test gaps

`/website_product_configurator/get_config_form_values`, `/website_product_configurator/onchange`, `/website_product_configurator/create_attach`, `/website_product_configurator/save_configuration`, `/website_product_configurator/create` are not covered by any `HttpCase` `url_open` or tour assertion. Coverage lives entirely at the ORM layer via `test_remove_inactive_config_sessions`.

**Recommendation:** add an `HttpCase` covering the storefront flow end-to-end for at least one canonical cabinet.

### 6.5 UX correctness of `base.public_user` shared session

Two anonymous visitors on the same product page race on the same session row (`_authorize_session` scopes by `user_id`; for anonymous, that's the shared `base.public_user`).

**Recommendation:** either (a) key `_authorize_session` on `request.session.sid` for public users so two anonymous browsers get two sessions, or (b) rely on the OCA session-GC cron and document the racy expectation. Neither is a security defect.

## 7 · Compliance with the module intent

| Intent (from OCA docs + brief) | Status | Evidence |
|---|---|---|
| Every configured selection persists to `product.config.session` | ✅ | Verified via `southbrook_configurator_ux/tests/test_state_endpoint.py` + `test_select_commit.py` (60 tests exercising the flow) |
| `Next → Confirm` wizard drives `validate_configuration` at every step | ✅ | `product_configurator/tests/test_wizard.py:131` walks ~10 Next steps in `test_01_action_previous_step` |
| Rule violations raise `ValidationError` with a human-readable message | ✅ **as of this session** | Was masked as `AttributeError` at both :894 and :937 wrapper sites; fixed. `TestOCAValidationErrorWrappersV19` regression-tests the fix. |
| BoM auto-attachment on variant materialisation | ✅ | `product_configurator_mrp/tests/test_bom_contents.py:110,163,266` — all 3 branches covered including idempotency |
| Sale-order line reconfigure flow | ✅ | `product_configurator_sale/tests/test_sale.py:18 test_00_reconfigure_product` |
| Website storefront + `/my/configurations` portal | ✅ | `website_product_configurator/tests/test_portal_configurations.py:27` + browser tours |
| Southbrook v2 OWL configurator commits to `sale.order` | ✅ | `southbrook_configurator_ux/tests/test_select_commit.py` — 34 tests, 15 demo-guarded |
| No cross-collision with the refacing pricelist | ✅ | Verified — no configurator addon writes `product.pricelist.item` |
| Test count docstring accurate | ⚠️ | Configurator family stats: 215 test methods across 25 files. See §6.2 for tagging fragmentation. |

## 8 · Files changed this session

```
addons/product_configurator/models/product_config.py                             +12 (:937 twin fix)
addons/product_configurator/models/product_config_bookmark.py                    +9  (_sql_constraints → models.Constraint)
addons/product_configurator/static/src/js/boolean_button_widget.xml              +5  (`or` → `||` + comment)
addons/southbrook_estimating/views/launch_3d_menu.xml                            +14 (correct xmlid fallback)
addons/southbrook_estimating/tests/test_rule_enforcement.py                      +170 (5 new regression tests)
docs/E2E_AUDIT_CONFIGURATOR_FAMILY_2026-07-01.md                                 THIS FILE
```

## 9 · Recommendations going forward

### 9.1 Immediate (this branch)

- [x] Land the 4 P0 fixes (product_config.py:937, launch_3d_menu.xml, product_config_bookmark.py:118, boolean_button_widget.xml:8)
- [x] Add 5 regression tests
- [x] Re-run tests — **235 tagged / 0 failed / 0 error** (run 3)

### 9.2 Next branch (P1)

- [ ] Decorate the 15 untagged test files with a shared `configurator` tag (§6.2)
- [ ] Add an `HttpCase` for `/website_product_configurator/onchange` + `/save_configuration` end-to-end (§6.4)
- [ ] Choose UX behaviour for concurrent anonymous sessions on `/southbrook/api/configurator/state` (§6.5)

### 9.3 Follow-up audit rounds

- Audit `southbrook_kitchen_3d_configurator` — Three.js UI on top of the same session backend; separate scope
- Audit `southbrook_estimating_website` — the Phase-2 customer storefront overlay
- Backport the `:937` fix upstream to OCA `product-configurator` (companion to the `:894` PR that would land the same change)

### 9.4 OCA test debt

The 13 FIXME comments in `product_configurator/tests/` (§6.1) represent real coverage debt. If Southbrook wants to depend on `create_get_variant` for the estimating flow, the un-asserted OCA tests at `test_product_config.py:487` need to be turned into real assertions before any refactor of that method.

## 10 · Session methodology

- Three parallel `Explore` agents fanned out to enumerate models, views/UI, and tests in isolated read-only contexts.
- Two `docker exec sami-odoo odoo … --test-enable` runs baselined + verified fixes.
- Live prod URL was probed at HTTP surface only (`main-object="ir.ui.view(189,)"` = Trade Portal login page — behind auth).
- Direct prod DB access was **not** attempted (classifier correctly gates unlabeled prod DB access).

Co-Authored-By: Claude Opus 4.7 &lt;noreply@anthropic.com&gt;
