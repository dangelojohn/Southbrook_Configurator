# CHANGELOG — `southbrook_estimating`

## 19.0.7.10.0 — 2026-07-10 — Code-review pass (Module #11)

### Fixed
- **[HIGH/functional] Order Builder "Configure Product" broken for non-admins.**
  Added missing ACL rows for `southbrook.config.template.picker` (sole entry
  point of `sale.order.action_config_start`). TransientModels are not exempt
  from `ir.model.access`; without a row every non-superuser hit `AccessError`.
  `security/ir.model.access.csv`.
- **[CRITICAL/functional] Refacing (CTHS) channel was a silent no-op.**
  `_compute_refacing_price` (custom routine #2, 35% margin target) was never
  invoked and `pricelist_refacing` had no items, so `channel='refacing'` fell
  through to `list_price`. Added a `_compute_price` override that dispatches to
  `_compute_refacing_price` only for items flagged `is_refacing_margin_target`
  (no effect on the other 5 channels), and a single global pricelist item so the
  engine reaches it. `models/product_pricelist.py`, `data/pricelists.xml`.
- **[HIGH/rendering] Shop Copy / Door Order PDFs rendered unstyled.**
  Replaced `var(--southbrook-*)` CSS custom properties (unsupported by the
  QtWebKit/wkhtmltopdf PDF engine) with literal hex/font values.
  `reports/southbrook_report_styles.xml`.
- **[MEDIUM/security] SSRF/local-file-read via Prodboard asset importer.**
  Added `_assert_safe_public_url` (http(s)-only; blocks private/loopback/
  link-local/reserved/multicast/metadata addresses) gating `_fetch_url`.
  `models/cabinet_archetype.py`.
- **[MEDIUM/correctness] Wrong cabinet-type labels from duplicate dict keys.**
  `DL` and `WO` were each defined twice in `_TYPE_LABELS`; de-duplicated and
  added a body-class-aware override (`_TYPE_LABELS_BY_BODY`) so both meanings
  are reachable. `models/cabinet_archetype.py`.
- **[HIGH/perf] Builder PO intake create-in-loop ×3.**
  `_parse_csv`, `_parse_json`, and `action_apply` now batch into a single
  `create()` each. `models/builder_po_intake.py`.
- **[HIGH/robustness] Spec-sheet report crashed on estimating-only install.**
  `env['website']` guarded with a company-logo fallback (`website` is not a
  declared dependency). `reports/signature_spec_sheet.xml`.

### Added
- SSRF-guard regression tests (block-list + public-IP allow).
  `tests/test_prodboard_asset_importer.py`.

### Notes (unchanged by design — owner decisions)
- No `ir.rule` tenant isolation added (internal reps intentionally share
  visibility; scoping is a business-policy decision).
- `res.partner.channel` write-access left open (locking to managers would block
  salespeople from setting a new dealer's channel).
- P2/P3/P4 compute batching and the imperative hard-validation defence-in-depth
  left as-is; see REVIEW_REPORT.md D3/D4.
