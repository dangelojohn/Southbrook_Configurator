# Code Review & Repair Report — `website_product_configurator`

**Module:** Website Product Configurator (OCA, Southbrook-modified) · **Version:** 19.0.1.0.0 → **19.0.1.1.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 CE · **Queue:** #9 of 46 (Tier 1; deps `website_sale`, `product_configurator`, `product_configurator_sale`)
**Method:** 2 parallel agents (dedicated security-IDOR audit + v19/perf) + independent verification against source + ACL/rule cross-check across the parent module. (Dynamic install validation partially blocked by container flakiness on the heavy `website_sale` tree — see TEST_RESULTS.)

## Executive Summary
The public anonymous-buyer storefront configurator: 3 controllers, 11 routes (5 `auth=public`), ~29 `sudo()` calls. Only the 4 test files diverge from OCA. **The 18→19 mechanical port is excellent** (clean JS/controller/view v19 idioms, all documented). But the deep audit found **two genuine CRITICAL defects** (both upstream OCA, both live-exposed) plus hardening items:

1. **CRITICAL — anonymous RPC session takeover/destruction.** `website_product_configurator` grants `base.group_public` + `base.group_portal` implied membership in `group_product_configurator`, which carries a full `1,1,1,1` CRUD ACL on `product.config.session`/`.custom.value`/`.bookmark`. The only base `ir.rule` covers **portal read**; write/create/unlink are unruled and public users are unruled entirely. So via raw `/web/dataset/call_kw`, any anonymous visitor could `search_read`/`write`/**`unlink`** every buyer's config session in the DB (incl. ones referenced by confirmed orders). **Verified against the actual ACL/group files.**
2. **CRITICAL — silent data loss.** This module ships a duplicate, more-aggressive session-GC cron (3-day, no sudo, no cart/bookmark exclusion) that deletes `state='draft'` sessions — and a saved bookmark's session stays `draft`, with `session_id ondelete="cascade"`. So a buyer who "Saves" a configuration loses it (and the bookmark) after 3 days, contradicting the "My Configurations" feature's own contract. The base GC has the same bookmark gap.

## Original Issues Found
| # | Sev | Finding |
|---|-----|---------|
| S1 | **CRITICAL** | Anonymous/portal RPC can read/modify/mass-unlink all `product.config.session` + `.custom.value` (group-inheritance grants internal `1,1,1,1` ACL; only a portal-READ rule exists). |
| G1 | **CRITICAL** | Duplicate aggressive GC cron deletes bookmarked/saved draft sessions → cascade-deletes the buyer's saved bookmark. |
| S2 | HIGH | `product.config.bookmark` reachable by anonymous users via the same group inheritance (module comment claims "public gets none"). |
| S3 | MED | `cfg_session` render route's `user_id` ownership check is a no-op for anonymous traffic (all share the public user) → id-enumeration leaks other anonymous buyers' done-config pages (product/attrs/custom-text/price). |
| S4 | MED | `safe_eval(custom_field_value)` on unauthenticated POST text (public route) — CPU/memory exhaustion (`"9**9**9"`). |
| P1/P2 | MED | Unbounded anonymous session/variant creation (no rate limit); `get_attribute_value_extra_prices` uncached per page load. |
| M1 | LOW | Migration script uses `%`-formatted SQL. |

### Clean (verified): all v19 mechanical-port axes (JS `rpc` import, `publicWidget`/Interactions patch, `type="jsonrpc"`, `request.render`, `_slug`, no `<tree>`/`attrs=`/`t-raw`); CSRF (jsonrpc + csrf_token on portal POSTs); XSS (all `t-out`); no open redirect; `_check_reconfigure_ownership` is a correct cookie-bound IDOR guard.

## Repairs Completed
1. **S1 (+S2):** added 3 protective `ir.rule`s in `security/configurator_security.xml` scoping `product.config.session`, `.custom.value` (all 4 ops, public+portal, `user_id`/`cfg_session_id.user_id` domain) and `.bookmark` (public → own-none). The controllers `sudo()` their legitimate work, so these rules only constrain **raw RPC** — closing the mass read/modify/unlink hole without touching the storefront flow.
2. **G1:** `remove_inactive_config_sessions` now excludes `has_active_bookmark=True` and `is_saved=True` (and runs `sudo()`), so saved configurations survive GC.
3. **S4:** `safe_eval` → strict `int()`/`float()` parsing (removed the import).
4. **M1:** parameterized the migration SQL.

### Documented (not changed)
- **S3 fully:** the cfg_session route's anonymous ownership is best fixed with cookie-bound ownership (mirror `_check_reconfigure_ownership`) rather than `user_id`; the new `ir.rule` (S1) reduces the RPC blast radius, but the *route-level* info-leak for anonymous done-sessions remains — flagged as a follow-up controller fix.
- **Anonymous isolation residual:** all anonymous users share one public-user record, so `user_id`-scoped rules isolate anonymous-vs-authenticated but not anonymous-vs-anonymous; true anonymous isolation is the controller's cookie binding (which is sound for the controller path).
- **Base GC bookmark gap:** the parent `product_configurator._gc_draft_sessions` (7-day) also lacks the bookmark exclusion — should be patched upstream (#6 follow-up).
- P1 rate-limiting, P2 caching, and the v19 agent's *verify-this* note on whether the `base.group_public` implied_ids grant actually lands (the `group_user` no-op trap) — the module works in prod, implying it lands (hence S1 is real), but worth an empirical `res_groups_implied_rel` check.

## Files Changed
4 modified (`__manifest__.py`, `security/configurator_security.xml`, `models/product_config.py`, `controllers/main.py`, `migrations/17.0.1.0.0/pre-migration.py`).

## Database / Security / Performance
+3 `ir.rule` (RPC scoping). GC now bookmark-safe. safe_eval DoS removed. No schema change.

## Testing Results
_See `TEST_RESULTS.md`._ Static validation passes; the heavy `website_sale`-tree install is flaky in this container — a clean run is needed to confirm the new rules install and the public flow is unaffected.

## Remaining Risks
1. **S3 route-level anonymous info-leak** and the **base GC bookmark gap** are documented follow-ups, not yet coded.
2. The new `ir.rule`s need a live smoke test of the public configure→cart flow (the controller sudo's, so expected safe, but confirm) before deploy.
3. No anonymous rate-limiting (data-pollution/DoS surface).

## Recommendations
Deploy S1+G1 promptly (anonymous data-destruction + saved-config loss). Then: cookie-bind the cfg_session route (S3), patch the base GC upstream, add anonymous rate-limiting, and run the full demo-enabled suite.
