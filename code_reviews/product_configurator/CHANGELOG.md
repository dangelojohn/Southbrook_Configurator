# Changelog — `product_configurator` (OCA, Southbrook-modified)

## 19.0.1.1.0 — 2026-07-10 (code review #6)

Excellent existing 18→19 port; targeted fixes only. No config-engine behavior
change. Deeper OCA-engine items documented for upstreaming.

### Fixed
- **JS (HIGH):** `boolean_button_widget.xml` bound `props.state` (nonexistent)
  → `state.value`; `isReadonly` (undefined) → `props.readonly`. The
  "Configurable" stat checkbox now reflects the real value.
- **Security (HIGH):** `product.template.mako_tmpl_name` (renders Mako = executes
  Python — RCE surface) gated with
  `groups="product_configurator.group_product_configurator_manager"`.
- **Correctness (MED):** added missing `@api.depends` to `_compute_currency_id`
  and `_compute_config_step_name` (were stale — never invalidated).

### Added — performance
- `index=True` on the hot config-lookup keys: `product.config.session`
  (`product_tmpl_id`/`user_id`/`state`), `product.config.line`/`.image`/
  `.step.line` `product_tmpl_id`, `product.config.domain.line`
  `attribute_id`/`domain_id`.

### Verified clean (no change)
Clean on all 13 v19 axes (no `_sql_constraints`/`name_get`/`<tree>`/`attrs=`/
legacy-JS; correct decorators). Config-rule engine is eval-free. Portal record
rules (session + bookmark) correctly scoped. The southbrook bookmark model is
the highest-quality file in the module.

### Documented (not changed — upstream candidates)
Rule-engine memoization (perf HIGH), variant-creation caps, multi-company
`company_id`, `literal_eval`→`int/float`, the OWL `innerHTML` widget anti-pattern,
dead unreferenced view, `search_variant` limit. See `REVIEW_REPORT.md`.
