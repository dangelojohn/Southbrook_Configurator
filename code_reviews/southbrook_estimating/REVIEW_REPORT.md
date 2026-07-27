# Code Review — `southbrook_estimating` (Module #11, Tier 2 — the estimating HUB)

**Version:** 19.0.7.9.0 → **19.0.7.10.0**
**Reviewed:** 2026-07-10
**Scope:** ~24,385 LOC — 25 model files, 2 controllers, 10 view files, 4 report files, 5 migrations, 2 JS + 1 OWL template, 40 test files, `security/ir.model.access.csv`, `data/*`, `__manifest__.py`.
**Method:** Two independent parallel audits (v19-compat + code, and security + performance), each grounded in file:line citations; every CRITICAL/HIGH claim re-verified by me against actual source and Odoo 19 CE core before any edit.

---

## Executive Summary

The estimating hub is a large, mature, and generally well-engineered module — it is the most depended-on custom addon in the stack (Tier 2). The two audits and my verification surfaced **7 real defects** (2 functional-CRITICAL/HIGH, 3 rendering/robustness, plus a latent data footgun and a batching class), all of which are now **fixed and validated**. A further set of findings were verified to be **design/business-policy decisions the owner must make** (record-rule tenant isolation, channel-field lockdown) and are documented as prioritized recommendations rather than applied unilaterally — consistent with the brief's "preserve business logic / don't assume" rule.

Install is clean on a fresh v19 CE DB; 276/284 tests pass and **all 8 remaining failures are cross-module test-isolation artifacts** (the hub's tests assume the full downstream southbrook stack + prod's own `product_configurator` copy are installed), not defects in this module. My changes introduced **zero regressions** and the fixes eliminated the 4 baseline QWeb-report errors.

---

## Original Issues Found

### Fixed

| # | Sev | Title | Root cause |
|---|-----|-------|-----------|
| F1 | HIGH (functional) | `southbrook.config.template.picker` has no ACL row | The wizard is the *sole* entry point for the Order Builder "Configure Product" button (`sale_order.py:220`, the C1 fix). TransientModels are **not** exempt from `ir.model.access` — a non-admin salesperson hits `AccessError`, defeating the very flow it was built for. Tests never caught it because `TransactionCase` runs as **superuser**. |
| F2 | CRITICAL (functional) | Refacing channel pricing was a silent no-op | `_compute_refacing_price` (custom routine #2, the 35%-margin CTHS rule) was defined but **never invoked** by Odoo's pricing engine, and `pricelist_refacing` had **zero items**. Any `channel='refacing'` partner silently fell through to bare `list_price`. |
| F3 | HIGH (rendering) | Shared report styles used CSS custom properties wkhtmltopdf can't resolve | `southbrook_report_styles.xml` defined `:root{--southbrook-*}` and consumed them via `var(...)`. QtWebKit (wkhtmltopdf) does not support CSS variables → Shop Copy / Door Order PDFs rendered with **no colours, borders, or zone highlights**. The module already documents "hex only" elsewhere (`southbrook_room.py:to_svg`, `signature_spec_sheet.xml`). |
| F4 | MEDIUM (security, SSRF/LFI) | `_fetch_url` had no scheme/host allow-list | `import_assets(allow_network=True)` is an `AbstractModel` method → bypasses ACL, callable by any authenticated internal user via RPC. `image_url` is writable by salespeople. `urlopen` would follow `file://` (local-file read) and RFC1918/metadata hosts (SSRF). |
| F5 | MEDIUM (correctness) | Duplicate dict keys in `_TYPE_LABELS` | `DL` (Drawerline→**Dresser Larder**) and `WO` (Wine Open→**Wall Open Display**) were each defined twice; Python silently keeps the last, so the first meaning was unreachable and some archetypes would show the wrong label. |
| F6 | HIGH (perf) | Create-in-loop ×3 in builder PO intake | `_parse_csv`, `_parse_json`, and `action_apply` each issued one `create()` per row/line. Builder POs (Mattamy/Great Gulf) are hundreds of rows → hundreds of individual INSERTs. |
| F7 | HIGH (robustness) | `env['website']` KeyError in `signature_spec_sheet.xml` | `website` is not a declared dep; the spec-sheet report crashed on an estimating-only install. (Fixed earlier in this review pass; also cleared 4 QWeb test errors.) |

### Documented for owner decision (NOT auto-applied)

| # | Sev | Title | Why not auto-fixed |
|---|-----|-------|--------------------|
| D1 | (design) | No `ir.rule` tenant isolation on `southbrook.room*` / `.order.analytics` / `.builder.po.intake*` | All internal salespeople share `group_sale_salesman` and currently see every order. Whether reps should be scoped to their own dealer/customer is a **business-policy decision** — the personas here are Southbrook *staff*, not the dealers themselves (dealers have no group in this addon's ACL at all). Adding record rules changes live access behaviour and could break reps covering for each other. Ready-to-apply rule file provided in recommendations. |
| D2 | (policy) | `res.partner.channel` / `tradesperson_tier` writable by any employee → self-grant dealer pricing | Locking to managers via `groups=` would prevent salespeople from setting a new dealer's channel during order building. Needs owner's call on who may set channel. |
| D3 | (perf) | Per-row product resolution (P2), per-line `_bom_find` (P3), per-order analytics `capture` (P4) | Correct-but-suboptimal compute methods; batching them is a restructure with real regression surface. Documented with exact fixes; low marginal value at typical order sizes. |
| D4 | (architecture) | Imperative hard-validation string-matching in `sale_order.py:241-298` re-derives declarative rules | The code's own comments justify it as defence-in-depth against direct-ORM bypass — a reasonable engineering call. Flagged per the brief's grep-for-`if series ==` acceptance criterion; left as-is. |
| D5 | (external dep) | `from southbrook_dims import panel_cut_list` not declared in manifest | Reached via `/srv/shared` on PYTHONPATH; wrapped in try/except (degrades to zero-rollup). Document as a deployment-environment dependency. |

---

## Repairs Completed

**F1 — ACL row** (`security/ir.model.access.csv`): added `access_southbrook_config_template_picker_{sales,manager}` granting `sales_team.group_sale_salesman` (rwc) and `group_sale_manager` (rwcu) on `model_southbrook_config_template_picker`.

**F2 — Refacing pricing wired** (`models/product_pricelist.py` + `data/pricelists.xml`): overrode `product.pricelist.item._compute_price` (verified v19 signature `(product, quantity, uom, date, currency=None, **kwargs)` against core `product_pricelist_item.py:570`) to dispatch to `_compute_refacing_price` **only** when `is_refacing_margin_target` is set — zero impact on the other 5 channels. Added one global `pricelist_refacing_item_global` item so the engine actually reaches the override.

**F3 — Inlined hex** (`reports/southbrook_report_styles.xml`): replaced every `var(--southbrook-*)` with the literal hex/font values already present in the old `:root` block; added a "do not reintroduce CSS variables in report styles" note citing the wkhtmltopdf constraint.

**F4 — SSRF guard** (`models/cabinet_archetype.py`): added `_assert_safe_public_url` (http(s)-only; rejects hosts resolving to private/loopback/link-local/reserved/multicast/unspecified addresses) called at the top of `_fetch_url`. Raises `ValueError`, which `_import_one`'s existing try/except records as a clean per-archetype failure.

**F5 — De-duplicated labels** (`models/cabinet_archetype.py`): removed the two shadowed keys; kept `DL=Drawerline` / `WO=Wine Open` as flat defaults; added `_TYPE_LABELS_BY_BODY = {("dresser","DL"):"Dresser Larder", ("wall","WO"):"Wall Open Display"}` and made `_compute_cabinet_type_label` body-aware (added `body_class` to `@api.depends`).

**F6 — Batched creates** (`models/builder_po_intake.py`): the three loops now accumulate a `vals_list` and issue one `create()` each.

**F7 — Website guard** (`reports/signature_spec_sheet.xml`): `env['website']…` now guarded with `if 'website' in env else env.company.logo`.

**Tests added:** `test_ssrf_guard_blocks_non_public_and_non_http_urls` + `test_ssrf_guard_allows_public_ip` (both pass).

---

## Files Changed
- `security/ir.model.access.csv` (+2 rows)
- `models/product_pricelist.py` (+ `_compute_price` override)
- `data/pricelists.xml` (+ refacing global item, comment update)
- `reports/southbrook_report_styles.xml` (var()→hex)
- `reports/signature_spec_sheet.xml` (website guard)
- `models/cabinet_archetype.py` (SSRF guard + import; label de-dup + body-aware compute)
- `models/builder_po_intake.py` (3 batched creates)
- `tests/test_prodboard_asset_importer.py` (+2 SSRF tests)
- `__manifest__.py` (version bump)

## Database Impact
- New ACL rows (additive; grant-only, no revocation).
- New `product.pricelist.item` on `pricelist_refacing` — makes the refacing channel compute a real price where it previously returned list_price. **This is a functional price change for refacing customers** (now hits the intended 35% margin). Flag for owner awareness before deploy.
- No schema/migration changes; no field additions.

## Security Improvements
- SSRF/LFI vector on the Prodboard asset importer closed (F4).
- Order Builder configure flow no longer requires superuser (F1).
- Residual: TOCTOU DNS-rebinding on `_fetch_url` (resolve→fetch re-resolves) — acceptable for the internal-operator threat model; noted. Tenant-isolation (D1) and channel-write (D2) remain owner decisions.

## Performance Improvements
- Builder PO intake: 3× create-in-loop → batched `create()` (F6). P2/P3/P4 documented (D3).

## Remaining Risks
- **F2 price change**: refacing customers now priced by the margin rule rather than list price — intended per Build Spec §6, but a live behaviour change; verify no refacing orders are mid-flight before deploy.
- **D1/D2**: if Southbrook wants per-dealer data isolation, record rules + channel-field lockdown must be added (owner decision).
- **D5**: `southbrook_dims` must be present on the deployment PYTHONPATH for panel rollups (silently zero otherwise).

## Recommendations (priority order)
1. Owner decision on **D1** (tenant isolation) — highest security lever if dealers/reps must be scoped.
2. Owner decision on **D2** (who may set `channel`).
3. Apply **D3** batching if builder-PO or large-order pricing becomes a latency concern.
4. Vendor or declare **D5** (`southbrook_dims`).
5. Swap the Signature-Series hex tokens (F3) once `SIGNATURE_SERIES_TOKENS.md` / artifact #7 lands.
