# Code Review — `southbrook_estimating_website` (Module #18, Tier 3)

**Version:** 19.0.31.3.0 → **19.0.31.4.0**
**Reviewed:** 2026-07-11
**Scope:** LARGEST module — ~7644 LOC Python (3 controllers: main.py 3701, room_api.py 1017, docs.py 63; NO models/) + ~14327 LOC JS. The customer-facing one-page configurator + `/my` portal Order Builder. Depends: southbrook_estimating, website_product_configurator, portal, southbrook_kitchen_3d_configurator.
**Method:** Two parallel audits (v19+JS; security+perf) + live install/upgrade validation + HEAD baseline.

## Executive Summary
The customer/portal-facing website. Both audits found strong foundations: **only 2 `auth="public"` routes** (both safe — static page + allowlisted marketing PDFs, no path traversal), **pricing fully server-side** (channel pricelist not client-writable — money vector closed), **IDOR properly closed** (`_southbrook_resolve_order` + `_get_room_scoped` ownership guards, existence-oracle collapsed to AccessError), **no XSS/eval**. JS uses the sanctioned `public_components` registry. v19-clean apart from `type="json"` (deprecation).

The real finding is a **HIGH privilege-escalation**: a portal customer/dealer could release an order to manufacturing. Fixed + guarded. v19 items fixed. Install/upgrade clean; **zero regressions** (2 pre-existing cross-module test failures confirmed on HEAD; my new security test passes).

## Fixed
| # | Sev | Title | Root cause |
|---|-----|-------|-----------|
| H1 | HIGH (priv-esc) | `send_to_manufacturing` released orders to the shop floor for portal callers | The action (`main.py:1961`) gated only on `order.state == 'sale'`, then `mrp.production.create` under `sudo()` — never checking the caller's role or `production_approval_state`. Since `_southbrook_resolve_order` grants the customer/dealer/parent partner (share=True) access, a portal user could POST `action_code=send_to_manufacturing` and materialize MOs with no rep sign-off, skipping the approval gate. |
| M1 | MEDIUM (PII) | `set-customer` let a portal caller backfill a stranger's contact by email | `main.py:888`, `auth="user"` (not internal-only), `_southbrook_resolve_customer(..., trusted=True)` backfills a matched-by-email partner's blank name/phone/street from the payload. |
| V1 | MEDIUM (v19) | `type="json"` on 34 routes | Deprecated alias → `type="jsonrpc"`. |
| V2 | LOW (v19) | `auth_passkey` inherit not in `depends` | `auth_template.xml:181` inherits it; auto_install-mitigated. Declared explicitly. |

## Repairs Completed
- **H1** — `send_to_manufacturing` now rejects `share=True` callers outright, and (when `southbrook_mrp_pm` is installed — guarded on field presence, since this Tier-3 module can't hard-depend on Tier-5) requires `production_approval_state == 'approved'`. New regression test `test_portal_user_cannot_send_to_manufacturing`.
- **M1** — `set-customer` rejects `share=True` callers (staff-only).
- **V1** — 34 routes `type="json"` → `type="jsonrpc"` (main.py ×26, room_api.py ×8).
- **V2** — added `auth_passkey` to `depends`.

## Documented (not applied — bounded / larger refactor)
- **HIGH-2** — self-serve variant creation (`main.py:1367,1900,1634,1487`) bypasses the OCA config-rule validation, so a rule-excluded combo shows a wrong (possibly cheaper) live price until `action_confirm` re-validates (which DOES catch it); also unbounded `product.product` creation = variant-table DoS. Bounded (illegal combos rejected at confirm; values constrained to the template's PTAVs). Fix = validate against `values_available` before create + GC orphan variants (4-site refactor in a 3700-LOC controller).
- **MEDIUM-2** — `/southbrook/docs/<slug>.pdf` renders wkhtmltopdf per cache-miss (public CPU-DoS). Pre-render to `ir.attachment` or rate-limit.
- **MEDIUM-3** — N+1 per-line `mrp.bom` search in `_build_southbrook_order_payload` (`main.py:3456`) + `send_to_manufacturing`. Batch `_bom_find(products=order.order_line.product_id)`.
- **LOW-1** — `/my/southbrook/order-builder/new` creates a `sale.order` on GET (CSRF). Make POST-only.
- **LOW-2** — session-create / add-line not rate-limited (design-mutate routes are).

## Database / Security / Performance
- No schema changes. Money vector CLOSED (verified server-side channel pricing). IDOR CLOSED (verified ownership guards). Portal→manufacturing escalation CLOSED (H1). PII backfill closed (M1). Perf items (HIGH-2 GC, MEDIUM-3 N+1) documented.

## Testing Results
- **Install + upgrade:** clean.
- **Tests:** HEAD baseline **1 failed / 1 error / 85**; after my changes **1 failed / 1 error / 86** — the +1 is my `test_portal_user_cannot_send_to_manufacturing`, which **passes**. **Zero regressions.**
- **Pre-existing (confirmed on HEAD, cross-module):** `test_bom_payload_per_line.test_panel_count_positive_for_seeded_line` (panel count needs `southbrook_dims` external dep) + `test_design_3d_tab.TestDesign3dTab` setUpClass (needs a downstream fixture). Pass in the full deployed stack.

## Recommendations (priority)
1. HIGH-2 — route customer variant creation through the OCA session commit (rules pre-quote) + GC orphan variants.
2. MEDIUM-3 — batch the per-line BoM search.
3. MEDIUM-2 — cache/rate-limit the public docs PDF.
4. LOW-1/2 — POST-only order creation; rate-limit session-create.
