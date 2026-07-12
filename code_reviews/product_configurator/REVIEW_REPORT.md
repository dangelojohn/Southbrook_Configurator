# Code Review & Repair Report — `product_configurator`

**Module:** Product Configurator (OCA, Southbrook-modified) · **Version:** 19.0.1.0.0 → **19.0.1.1.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 Community Edition
**Queue position:** #6 of 46 (Tier 0 — OCA-derived foundation of the estimating stack; deps `account`, `stock`)
**Review method:** 3 audit dimensions (v19-compat, security, performance) via 2 parallel agents + independent verification + live install/test on Odoo 19 CE (overlaying the southbrook version over the container's OCA copy, with guaranteed restore).

---

## Executive Summary

The OCA product configurator, ported 18→19 and locally modified by Southbrook (10 diverged files: 2 models, 1 JS widget, 7 tests). ~10,856 LOC.

**This is an exceptionally well-done v19 port** — clean on *every* v19-breakage axis: no `_sql_constraints` (correctly migrated to `models.Constraint`), no `name_get` (correctly `_compute_display_name`), no `<tree>`/`attrs=`/`states=` (fully ported view layer), correct `@api.model_create_multi`, correct `group_ids`/`name_search(domain=...)` renames, no legacy JS (`odoo.define`/`useService("rpc")`). The southbrook additions — a saved-config **bookmark** model and **portal record rules** — are the highest-quality files in the module. And notably, the config-rule engine is **eval-free** (structured id-set arithmetic, not expression evaluation) — the standout security positive for a data-driven configurator.

The real findings were a JS widget bug (in a southbrook-diverged file), two missing-`@api.depends` computes (OCA-original), missing indexes, and an upstream-OCA Mako-template RCE surface. Fixed the localized ones; documented the deeper OCA-engine items (which should ideally be upstreamed — this module carries OCA PRs).

---

## Original Issues Found

| # | Sev | Axis | Finding |
|---|-----|------|---------|
| J1 | **HIGH** | v19/JS | `static/src/js/boolean_button_widget.xml` bound `value="props.state \|\| false"` — `props.state` doesn't exist (should be `state.value`, which the widget's own JS already uses) → the "Configurable" checkbox always rendered false; `disabled="isReadonly"` referenced an undefined getter. (Southbrook-diverged file.) |
| S1 | **HIGH** | Security | `product.template.mako_tmpl_name` renders **Mako** (executes Python `<% %>`) when a variant name is computed — an RCE surface with no manager-group gating (inherits broad `product.template` write ACL). Upstream OCA. |
| P1 | **HIGH** | Perf | Rule engine (`values_available` → `compute_domain`/`validate_domains_against_sels`) re-evaluated per attribute-value in nested loops on every wizard onchange — O(attributes × values × config_lines) redundant work, unmemoized. Upstream OCA. |
| P2 | MED | Perf | Missing `index=True` on the hot config-lookup keys: `product.config.session` (`product_tmpl_id`/`user_id`/`state` — the every-wizard-open lookup on a 100k+/month table), `product.config.line`/`.image`/`.step.line` `product_tmpl_id`, `product.config.domain.line` `attribute_id`/`domain_id`. |
| C1 | MED | Correctness | `_compute_currency_id` and `_compute_config_step_name` had **no `@api.depends`** → stale (never invalidated). Upstream OCA. |
| S2/S3 | MED | Security | No `company_id`/multi-company rule (cross-company exposure); unbounded self-service variant creation (data-pollution/DoS). Upstream OCA. |
| — | LOW | — | `literal_eval` on custom values (uncaught-exception, not RCE); dead unreferenced `config_step_tree_view`; unbounded `search_variant`. |

### Reviewed and found clean
All 13 v19 axes (see above), ACL completeness (bookmark rows added for all tiers), portal record-rule isolation (session + bookmark scoped to `user_id=user.id`), **eval-free rule engine**, no SQL injection, no positional `sudo()`.

---

## Repairs Completed
1. **J1:** widget template `value="state.value"` + `disabled="props.readonly"` (verified consistent with the widget's own `this.state.value` usage; it `extends BooleanField`).
2. **S1:** `mako_tmpl_name` gated with `groups="product_configurator.group_product_configurator_manager"` — only configurator managers can read/write the code-executing field.
3. **P2:** `index=True` added to all 6 hot config-lookup fields (matching what `product_config_bookmark.py` already does).
4. **C1:** `@api.depends("config_step")` on `_compute_config_step_name`; `@api.depends("product_tmpl_id", "product_tmpl_id.company_id.currency_id")` on `_compute_currency_id`.

### Deliberately NOT changed (documented — should be upstreamed to OCA)
- **P1 rule-engine memoization** (perf HIGH): the fix (memoize `compute_domain()` per `domain_id` within a call) touches the core OCA rule engine; deferred to avoid risking config-correctness on a module I can't fully test here (demo-dependent test suite). Documented with the specific approach.
- **S2 variant caps / S3 multi-company**: design-level; deferred (single-company deployment; caps need a policy).
- `literal_eval`→`int/float` hardening; the OWL `innerHTML` anti-pattern in the widget (`updateConfigurableButton` manually mutates an OWL-managed subtree — a latent trap, but the minimal binding fix is applied); dead view removal; `search_variant` limit. All LOW; documented.

---

## Files Changed
4 modified (`__manifest__.py`, `models/product.py`, `models/product_config.py`, `static/src/js/boolean_button_widget.xml`). The southbrook divergences (bookmark model, record rules) needed **no** fixes.

## Database Impact
6 new indexes on the config tables (created on upgrade; low cost). The Mako `groups=` narrows field visibility (no data change). Forward-compatible.

## Security Improvements
Closed the Mako RCE exposure (manager-gated). Confirmed the rule engine is eval-free and portal isolation is correctly enforced by record rules.

## Performance Improvements
6 indexes on the every-wizard-open lookup keys. (The larger rule-engine memoization is documented for a follow-up/upstream PR.)

## Testing Results
_See `TEST_RESULTS.md`._ Installs cleanly on v19; after all fixes the suite is unchanged at **0 failed, 15 error(s)** — the 15 errors are **exclusively `bmw_2_series` demo-data-not-loaded** (the local CI container doesn't load demo data; these pass in OCA CI/prod), NOT defects. My changes introduced **zero new failures** (the ~19 non-demo tests, incl. bookmarks, still pass). 6 indexes confirmed in the DB.

## Remaining Risks
1. The rule-engine perf (P1) is real user-facing lag on a large catalog — schedule the memoization as a follow-up (ideally an OCA PR).
2. Multi-company / variant-cap items if the deployment scales beyond one company / needs abuse protection.
3. The demo-dependent tests couldn't be exercised in this harness — run the full suite in a demo-enabled env before deploy.

## Recommendations
- Upstream the fixes (indexes, Mako gating, `@api.depends`, JS binding) to the OCA fork's PRs.
- Implement the rule-engine memoization (documented approach) — biggest UX win for the estimating configurator.
- Run the demo-enabled test suite in CI to cover the config-rule/variant-create paths this container can't.
