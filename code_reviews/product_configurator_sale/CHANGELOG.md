# Changelog — `product_configurator_sale` (OCA, Southbrook-modified)

## 19.0.1.1.0 — 2026-07-10 (code review #8)

Clean v19 port; one MEDIUM data-integrity fix. No v19-compat issues.

### Fixed
- **MEDIUM (data integrity):** `config_session_id` on `sale.order.line` made
  `readonly="1"` in both view locations (`views/sale_view.xml`). It is meant to
  be set by the configurator wizard (server-side write, unaffected by view
  readonly); the field was previously hand-editable, letting a user repoint a
  line's price/description at a different product's config session.

### Verified clean (no change)
- All v19 axes. The `_compute_price_unit` `@api.depends` override is SAFE —
  Odoo unions `@api.depends` across the MRO for a shared compute method
  (verified against core `Field.get_depends`/`resolve_mro`), so core's
  price triggers (product/uom/qty) are preserved, not replaced.
- Security clean: buttons gated to `group_product_configurator`, unreachable by
  portal/public; zero `sudo`/`eval`/SQL. Performance clean (no N+1/variant loop).

### Documented (not changed)
Misleading `..._manager` ACL row name (grants `group_product_configurator`);
optional `index=True` on `config_session_id`; a stricter `@api.constrains`
(product↔session match) as a follow-up. See `REVIEW_REPORT.md`.
