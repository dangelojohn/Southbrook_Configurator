# Code Review — `southbrook_kitchen_mrp` (Module #22, Tier 4)

**Version:** 19.0.1.5.1 → **19.0.1.6.0**
**Reviewed:** 2026-07-11
**Scope:** ~3204 LOC, no controllers, no JS — cut lists, hardware/production packages, catalog BoM generation (a cron), nesting-envelope I/O, QR kind-handlers, a cabinet-label QWeb PDF. Models: mrp_bom_catalog, mrp_production, qr_kind_handlers, sb_cutlist, sb_hardware_package, sb_production_package. Depends: mrp, sale, southbrook_estimating, southbrook_hardware_catalog, southbrook_freecad_bridge, southbrook_qr_kit.
**Method:** Two parallel audits (v19+code; security+perf) + live install/upgrade/test validation + HEAD baseline.

## Executive Summary
A **well-defended, well-built** module. The security audit found the three prioritized concerns all **clean by design**: nesting I/O is pure dict-in/dict-out (no SSRF/path/eval — the `from_nesting_result` payload is schema-allowlisted + type-checked), the BoM catalog cron is underscore-private (not RPC-triggerable), cron-root, idempotent, and never mutates/empties an existing BoM, and QR dispatch is HMAC-signed + ACL-gated (no IDOR). No `eval`/SQL/`sanitize=False`/XSS; the label uses `t-out` + hex-only CSS; ACL complete; the hardware-`resolve()` N+1 is already batched and FK indexing is complete.

The one serious bug was a **HIGH feature-breaker**: the cabinet-label PDF crashed on **every** print (`hasattr` unavailable in the QWeb context). Fixed + 3 MEDIUM/LOW. Install + upgrade clean; the HIGH label crash is fixed (its test went ERROR→PASS); **zero regressions** (1 pre-existing `southbrook_dims` failure, confirmed on HEAD).

## Fixed
| # | Sev | Title | Fix |
|---|-----|-------|-----|
| H1 | HIGH (feature-break) | Cabinet Label PDF crashed on every render — `reports/cabinet_label_report.xml:330` used `hasattr(o,'pg_revision_code')`, but `hasattr` is NOT in the `ir.qweb` report eval context (only in mail templates) → `TypeError: 'NoneType' object is not callable` on 100% of prints | `'pg_revision_code' in o._fields and o.pg_revision_code` (`in` + `_fields` are QWeb-legal); also fixed the test's naive `assertNotIn('sbk-rev-row')` (matched the CSS class, not the row) → `<tr class="sbk-rev-row"` |
| M1 | MEDIUM (UX) | No `ir.sequence` records shipped → `next_by_code(...) or _("New")` fell to "New" for EVERY cutlist/hardware/production package | added `data/ir_sequence.xml` with the 3 sequences (`CUT/`, `HWP/`, `PKG/` prefixes) |
| M2 | MEDIUM (robustness) | `qr_kind_handlers.py:47` calls `record.record_scan()` — a method from `southbrook_floor_traveler` (can't be a dep — dependency loop) → `AttributeError` if a `pkg` QR is scanned without it | `hasattr` guard → clean `UserError` |
| L4 | LOW (observability) | `from_nesting_result` scrap-create `except Exception: pass` swallowed failures silently (comment claimed it logged) → cutlist flips to `nested` with zero scrap, no trace | now `_logger.warning`s the failure |

## Documented (not applied)
- **MEDIUM (cross-module)** — a signed `pkg` QR + a read-only `mrp_user` reaches `wo.sudo().button_finish()` in **`southbrook_floor_traveler`**, bypassing WO write-ACL. The fix belongs to that module (a designed shop-floor advance, but a genuine sudo bridge) — will address in the `southbrook_floor_traveler` review.
- **MEDIUM (multi-company)** — cutlist/package models have no `company_id`/record rule (cross-company read/write if multi-company is ever enabled; single-company Southbrook → LOW-effective).
- **MEDIUM (hardening)** — public RPC orchestration methods (`from_nesting_result`, `generate_from_mo`, `build_from_order_line`, `generate_lines_from_*`) are `mrp_user`-callable (ACL-bounded, not escalations; the destructive `generate_from_mo` rebuild is already manager-gated by the unlink ACL). Prefix internal ones with `_` or gate behind an action.
- **MEDIUM** — undeclared top-level `from southbrook_dims import panel_cut_list` (`sb_production_package.py:13`) — a `/srv/shared` PYTHONPATH hard-dep with no manifest declaration (works on prod; make lazy or document).
- **LOW** — `tracking=True` on `state` fields without `mail.thread` = silent no-op; catalog/cutlist/hardware create-in-loop (bounded); `_check_unique_mo` TOCTOU (no DB constraint); offcut N+1 (cap the client-supplied list).

## Testing Results
- **Install + upgrade:** ✅ clean. v19-CLEAN (cron v19-schema, `models.Constraint`, `@api.model_create_multi`, all form-inherit xpaths resolve, hex-only label CSS, lazy qrcode/PIL).
- **Unit tests:** **1 failed / 0 error / 39** (install + upgrade). HEAD baseline was **1 failed / 1 error** — the label-render ERROR (the `hasattr` crash) is **fixed** (now passes); zero regressions.
- **Pre-existing (confirmed on HEAD):** `test_build_from_order_line.test_emits_exactly_one_package_with_non_empty_cutlist` — the cutlist comes back empty from `southbrook_dims.panel_cut_list` for the test cabinet (a shared-dims data/version artifact, like the freecad-bridge dims parity drift). Unrelated to these changes.

## Recommendations (priority)
1. Reconcile the `southbrook_dims` panel-count contract so `test_build_from_order_line` produces a non-empty cutlist (shared-module data drift).
2. Address the cross-module `pkg`-QR sudo WO-finish in `southbrook_floor_traveler`.
3. Make `southbrook_dims` import lazy / declared; `_`-prefix or action-gate the RPC orchestration methods.
