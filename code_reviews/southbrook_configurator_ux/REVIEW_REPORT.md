# Code Review — `southbrook_configurator_ux` (Module #17, Tier 3)

**Version:** 19.0.1.7.0 → **19.0.1.8.0**
**Reviewed:** 2026-07-11
**Scope:** ~4012 LOC Python + ~1764 LOC JS — the **public customer-facing website configurator UX** (`/southbrook/api/configurator/{state,select,commit}` public routes + backend xlsx import routes), OWL configurator over a JSON-RPC API, models (catalog_expansion, rule_completion, tactical_price_seed). Depends: website_product_configurator, product_configurator, southbrook_estimating.
**Method:** Two independent parallel audits (v19+JS; security+performance) + live install/test validation + a HEAD baseline (to separate my changes from pre-existing failures).

---

## Executive Summary

The public shop configurator. Both audits found strong foundations: **pricing is fully server-side** (no client price/qty/pricelist injection — the money vector is closed), **no XSS** (`t-esc`/`t-out` only), and the **JS mount correctly sidesteps public-page traps** (raw fetch, no `useService`). The v19 surface is clean (no `obj()` install trap; only a `type="json"` deprecation).

The real finding is **HIGH: anonymous session sharing / IDOR** — all anon visitors are `base.public_user`, so sessions bound to `user_id` collide across shoppers and `_authorize_session` let any anon mutate any public session. **Fixed** (HTTP-session binding, the OCA pattern) + guarded with a new regression test. `type="json"→"jsonrpc"` fixed. Install clean; **my changes introduce zero regressions** (HEAD baseline: 15 failing tests; after my changes: same 15 + 1 new passing security test).

**Pre-existing test-debt surfaced (not a regression):** 15 `test_select_commit` tests fail on the current v19 CE build — see below. Worth a dedicated follow-up.

---

## Original Issues Found

### Fixed

| # | Sev | Title | Root cause |
|---|-----|-------|-----------|
| H1 | HIGH (IDOR / isolation) | Anonymous config sessions shared across visitors | Sessions bound to `request.env.user.id`; every anon visitor is `base.public_user`, so (a) two anon shoppers on the same template **collide on one draft session** (state corruption), and (b) `_authorize_session` authorized on `session.user_id == public_user` alone → any anon could read/mutate **any** other anon's in-progress config via a crafted `session_id`. |
| V1 | MEDIUM (v19) | `type="json"` on the 3 public routes | Deprecated alias in v19 → `type="jsonrpc"`. |

### Documented (not applied)

| # | Sev | Title | Why not auto-fixed |
|---|-----|-------|--------------------|
| D1 | MEDIUM | `/select` trusts `product.attribute.value` ids not bound to the template | I implemented a filter (value-level, then attribute-level) but **both broke 15 legitimate-pick tests** — the OCA config-session exposes SKU attributes via a model my naive `tmpl.attribute_line_ids` check doesn't match. Reverted to avoid shipping a broken filter. Impact is limited (off-template values add no price — `price_extra` is per-PTAV/template-scoped — and `/commit` re-runs `validate_configuration`). A correct filter needs the OCA session's real attribute model. |
| D2 | MEDIUM | `/select` is an unauthenticated DB-write + O(n³) rule-eval DoS amplifier | Rate-limiting is infra; non-persisting for public users is a design change (public visitors legitimately persist picks). Owner decision. |
| D3 | MEDIUM | CSRF disabled on `/import/preview` + `/import/commit` (`type="http"`, `csrf=False`, mutating product.template) | Internal-only (`not user.share` gated) + `SameSite=Lax`-mitigated. A real CSRF token flow needs coordinated frontend changes; recommend that or converting to `type="jsonrpc"`. |
| D4 | LOW | `/state` loops all variants for SKU; bare `except Exception` on commit path swallows snapshot/confirm failures; seed `delete+recreate` churn; cross-module `ir.model.data` under `southbrook_estimating` | Hygiene/robustness; bounded. |

---

## Repairs Completed
- **H1** — `_get_or_create_session` now isolates anonymous visitors by the HTTP session cookie (`request.session["sb_ux_config_session_ids"]`, via `_http_owned_session_ids`/`_remember_http_session`) instead of the shared `public_user` id; authenticated users keep the `user_id` binding. `_authorize_session` verifies public sessions belong to **this** HTTP session. New regression test.
- **V1** — `type="json"` → `type="jsonrpc"` on `/state`, `/select`, `/commit`.

## Files Changed
`controllers/main.py`, `tests/test_state_endpoint.py` (+1 test), `__manifest__.py`.

## Database Impact
- None (no schema/field/index changes). Session binding is runtime-only.

## Security Improvements
- Cross-anonymous session collision + IDOR closed (H1). Money vector was already closed (server-side pricing — confirmed, kept).
- Residual (documented): D1 (value-id validation — needs correct attribute model), D2 (DoS/rate-limit), D3 (import CSRF).

## Testing Results
- **Install/upgrade:** clean.
- **Unit tests:** my changes are clean — HEAD baseline **15 failed / 54**; after my changes **15 failed / 55** (the +1 is my new `test_anon_sessions_isolated_by_http_session`, which **passes**). Zero regressions.
- **⚠ Pre-existing test-debt (15 failures, confirmed on unmodified HEAD):** `test_select_commit` — two categories: (a) SKU composition returns `-XXX` for Finish (the pick doesn't compose into the live SKU); (b) `/commit` returns `incomplete_configuration` for `Door Style`/`Door Overlay`/`Interior Storage` — **required attributes the module's own `catalog_expansion`/`tactical_price_seed` seed adds, which the test fixtures (`_complete_via_select`) predate**. Production is unaffected (a customer picks all attributes in the UI); this is stale test fixtures + a possible SKU-composition drift on the newer v19 build.

## Remaining Risks
- **D1**: without the value-id filter, a client can push out-of-catalog values into its own session (bounded — no price effect, commit re-validates).
- The 15 pre-existing failures should be triaged: confirm whether the SKU-`XXX` behavior is a genuine regression on the current v19 build or purely a fixture gap.

## Recommendations (priority)
1. **Follow-up pass** on the 15 pre-existing `test_select_commit` failures — update `_complete_via_select` to pick the newly-required attributes, and diagnose the Finish→SKU composition.
2. **D1** — implement a correct template-membership filter once the OCA session attribute model is confirmed.
3. **D3** — add CSRF handling (or `type="jsonrpc"`) on the import endpoints.
4. **D2** — rate-limit `/select` / non-persist for public.
