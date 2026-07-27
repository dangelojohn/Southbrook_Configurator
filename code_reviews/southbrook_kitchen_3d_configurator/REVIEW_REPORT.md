# Code Review — `southbrook_kitchen_3d_configurator` (Module #16, Tier 3)

**Version:** 19.0.5.6.15 → **19.0.5.7.0**
**Reviewed:** 2026-07-11
**Scope:** ~4564 LOC Python (models: kitchen.design, product_template, reconcile, sale_order/line/cancel_sync, southbrook_room; a **web controller**) + ~3666 LOC JS (OWL + vendored Three.js r160 canvas). Depends: web, product, sale_management, stock, mrp, mail, southbrook_estimating.
**Method:** Two independent parallel audits (v19+JS+code; security+performance) + **live install/upgrade validation** (which caught a CRITICAL both agents missed).

---

## Executive Summary

The large 3D kitchen configurator. The JS/OWL surface (24 esm modules + the client action) is **v19-clean** (correct `rpc`/`user` imports, backend client action — not a public mount), and the controller has **zero `auth="public"` routes** (all `auth="user"`). But three real issues surfaced: a **CRITICAL v19 install-blocker** (only caught by running install), a **customer-facing pricing money-vector**, and an **undeclared cross-tier field crash**.

Fixed: **1 CRITICAL (install), 1 HIGH (money-vector), 1 HIGH (cross-tier robustness), 3 MEDIUM, 1 v19-deprecation**. Module now **installs on v19 CE** (it did not before) and passes **28/28 tests** including a new money-vector regression test.

---

## Original Issues Found

### Fixed

| # | Sev | Title | Root cause |
|---|-----|-------|-----------|
| C1 | **CRITICAL** (install) | Module failed to install on current v19 CE | `security/groups.xml:47` swept every internal user into Manager via `<value eval="...obj().env['res.users'].search(...)">`. In v19, `obj` is **not** injected into a `<value>` child of `<function>` (the `<value>` node has no `model=`, so `_get_eval_context` skips it) → `NameError: name 'obj' is not defined` → **registry load failure**. Both audit agents verified the field names but not the eval-context availability; **live validation caught it.** (Prod runs an older 19.0 build where `obj` still existed.) |
| H1 | HIGH (money-vector) | `save_design` trusted a client-supplied price into the quote | `controllers/main.py` set the design line's `price_unit` to `item.get("price")` (client value), which flows verbatim into the `sale.order.line` at `action_create_quotation` (the explicit `price_unit` is honoured over the pricelist per v19 precompute semantics). A tampered client could set its own price. Latent-CRITICAL: `auth="user"` limits it to internal reps today, but the engine is described as customer-facing and the sibling website layer exposes it. |
| H3 | HIGH (robustness) | `action_create_quotation` crashed without `southbrook_mrp_pm` | `kitchen_design.py:1264` wrote `force_production_release` — a field defined only in `southbrook_mrp_pm` (Tier 5) — with no guard, so this Tier-3 module `ValueError`d when mrp_pm wasn't installed (it can't hard-depend on Tier 5 without inverting the tier order). |
| M1 | MEDIUM (IDOR) | `save_design` lacked the `check_access` its siblings enforce | The `design_id` branch did `browse().write()` with no `exists()`/`check_access("write")` (unlike save_position/delete_line), and wrote the raw client `partner_id` (a user could stamp any partner and drive pricelist off it). |
| M2 | MEDIUM (perf) | N+1 in `save_design` | One ACL-respecting `Product.search()` per incoming item (40-60 queries on a large save). |
| M4 | MEDIUM (perf) | Missing indexes | `kitchen.design.sale_order_id` / `partner_id` (busy FK filters on every SO-cancel/navigation) were unindexed. |
| V1 | MEDIUM (v19) | `type="json"` on all 7 routes | Deprecated alias in v19 (functional, warns) → `type="jsonrpc"`. |

### Documented (not applied)

| # | Sev | Title | Why not auto-fixed |
|---|-----|-------|--------------------|
| D1 | HIGH (policy) | `group_kitchen_manager` sweep nullifies per-designer isolation | The sweep (now v19-valid) is a **deliberate, documented** "pre-tax­onomy full-access default" — every internal user gets full access, defeating the `create_uid` record rule. Retiring it (for isolation) is a **business-policy decision** (reps lose all-designs visibility; new users would get no access until granted). Kept the behaviour, documented the choice. |
| D2 | MEDIUM (perf) | `qty_available` + per-product `_get_product_price` in `/products`/`/layout` | N stock rollups + N pricelist resolutions per catalog fetch. Tolerable at ~11 cabinets; batch when the catalog grows. |
| D3 | LOW | `zone` field `default="base_run"` masks its own compute | The default pre-fills so `_compute_zone`'s `if not line.zone` guard never derives from `cabinet_type` (a migration already fixed existing DB data). Dropping the default fixes new lines, but it's a `required` field in a module I'm already heavily editing — deferred to avoid regression risk. |
| D4 | LOW | `cron_reconcile_designs` RPC-reachable (sudo cascade); `_ensure_kitchen_bom` mrp sudo; `@api.constrains` that writes `zone_label` | Bounded/internal; hygiene. |

---

## Repairs Completed
- **C1** — moved the user-sweep into `models/res_groups.py::_southbrook_kitchen_sweep_managers` (real `self.env`); `groups.xml` now calls it argument-free. Install works on v19 CE.
- **H1** — `save_design` resolves the channel pricelist once and prices each line via the existing `_channel_price(product, pricelist, partner)` helper; the client `item["price"]` is never persisted. New regression test.
- **H3** — guarded the `force_production_release` write with `"force_production_release" in order._fields`.
- **M1** — added `exists()` + `check_access("write")` (graceful degrade) to the `design_id` branch; persist the ACL-validated partner (`_browse_partner(...).id`) not the raw client id.
- **M2** — batched the per-item catalog lookup into one `search([("id","in",…), cabinet, sale_ok])` + dict.
- **M4** — `index=True` on `sale_order_id` and `partner_id`.
- **V1** — `type="json"` → `type="jsonrpc"` on all 7 routes.

## Files Changed
`controllers/main.py`, `models/kitchen_design.py`, `models/res_groups.py` (new), `models/__init__.py`, `security/groups.xml`, `tests/test_save_design_acl.py` (+1 test), `__manifest__.py`.

## Database Impact
- New indexes on `sale_order_id`/`partner_id` (additive). The user-sweep still runs on -i/-u (now via Python) — same grant behaviour as before.

## Security Improvements
- Module actually installs (C1). Client can no longer set its own quote price (H1). `save_design` IDOR now matches its siblings + validates partner (M1).
- Residual (documented): D1 (isolation policy), D4 (cron/mrp sudo).

## Performance Improvements
- `save_design`: N catalog searches → 1 (M2). `sale_order_id`/`partner_id` indexed (M4).

## Remaining Risks
- **D1**: with the sweep intact, there is no per-designer isolation — every internal user sees/edits every design. Retire the sweep (owner decision) to enforce it.
- **H1 note**: fix closes the save path; if any route is ever exposed to portal customers, re-audit `_resolve_channel_pricelist` for client-supplied `partner_id`.

## Recommendations (priority)
1. **D1** — decide whether to retire the manager sweep for per-designer isolation.
2. **D2** — batch catalog pricing/qty when the cabinet catalog grows.
3. **D3** — drop the `zone` default so the compute derives per `cabinet_type`.
