# Code Review & Repair Report — `product_configurator_sale`

**Module:** Product Configurator Sale (OCA, Southbrook-modified) · **Version:** 19.0.1.0.0 → **19.0.1.1.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 CE · **Queue:** #8 of 46 (Tier 1; deps `sale_management`, `product_configurator`, `stock`)
**Method:** combined audit agent (v19/security/perf, verified against core source) + independent verification + live overlay install/test on Odoo 19 CE.

## Executive Summary
Small (~659 LOC) OCA bridge: lets a `sale.order.line` be configured via the product-configurator wizard. Only the 2 test files diverge from OCA (models/views/wizard are pristine). **Clean on every v19 axis, clean on security (no portal exposure, no `sudo`/`eval`/SQL), clean on performance.** No CRITICAL/HIGH findings. One MEDIUM data-integrity gap fixed.

Notably: the agent verified against core (`Field.get_depends`/`resolve_mro`) that Odoo **unions** `@api.depends` across the MRO for a shared compute method — so the `_compute_price_unit` override's depends `(config_session_id, tax_ids, company_id)` are *merged* with core's `(product_id, product_uom_id, product_uom_qty)`, not replaced. (I had flagged this as a possible stale-price bug; verification confirmed it is safe — the documented OCA extension pattern.)

## Original Issues Found
| # | Sev | Finding |
|---|-----|---------|
| 1 | **MEDIUM** | `config_session_id` on `sale.order.line` (`views/sale_view.xml:24,41`) had no `domain`/`readonly`/constraint — an internal user could hand-edit it to point a line's price/description at a *different* product's config session (bypassing pricelist/attribute pricing), a data-integrity gap. The shipped test even exercises the reassignment. |
| 4 | LOW | ACL row `access_product_configurator_sale_manager` (`ir.model.access.csv:3`) is named "_manager" but grants `group_product_configurator` (all employees). Functionally correct (transient wizard needs create); misleading name only. |
| 7 | LOW | `config_session_id` unindexed (optional; only matters if a future report filters SO lines by session). |
| 2 | LOW/note | The Mako-template RCE surface is reached via this module's create-line path but lives in `product_configurator` (already gated to configurator-managers there — see module #6's fix). No action here. |

### Clean (verified): all v19 axes (incl. the `@api.depends` union, `.onchange()` v19 signature, `_fix_tax_included_price_company` present); security (buttons gated to `group_product_configurator`, unreachable by portal/public; zero `sudo`); performance (no variant-creation loop, no N+1 — recordset iteration preserves prefetch; no unbounded search).

## Repairs Completed
1. **#1:** made `config_session_id` `readonly="1"` in both view locations (form + editable list). It's meant to be set by the wizard flow (server-side write, unaffected by view readonly), not hand-edited — closes the price/description-swap gap without breaking the wizard or the tests.

### Documented (not changed)
- #4 misleading ACL row name (cosmetic — a rename with no behavior change).
- #7 optional `index=True` on `config_session_id`.
- A stricter `@api.constrains(config_session_id.product_id == product_id)` would be more robust than readonly but risks breaking legitimate reassignment flows / the existing test — deferred in favor of the low-risk readonly.

## Files Changed
2 modified (`__manifest__.py`, `views/sale_view.xml`).

## Database / Security / Performance
No schema change. Security: closed the hand-edit data-integrity gap (readonly). No perf changes needed.

## Testing Results
_See `TEST_RESULTS.md`._ Installs cleanly on v19; no regressions. (Config-flow tests inherit the `bmw_2_series` demo-data dependency the local container doesn't load — environment limitation, not a defect.)

## Remaining Risks
Minor: the readonly guard prevents UI editing but not a server-side ORM write of a mismatched session (rare, internal-only) — a `@api.constrains` would fully close it if desired.

## Recommendations
Upstream the readonly guard; consider the `@api.constrains` and the ACL-row rename as follow-ups.
