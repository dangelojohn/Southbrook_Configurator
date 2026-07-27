# Changelog — `website_product_configurator` (OCA, Southbrook-modified)

## 19.0.1.1.0 — 2026-07-10 (code review #9)

Excellent 18→19 port; two CRITICAL defects fixed (both upstream OCA, both
live-exposed on the public storefront).

### Fixed
- **CRITICAL (security) — anonymous RPC session takeover:** `base.group_public`
  / `base.group_portal` inherit `group_product_configurator`'s full `1,1,1,1`
  CRUD ACL on `product.config.session`/`.custom.value`/`.bookmark`, and the base
  ir.rule only covered portal READ — so raw `/web/dataset/call_kw` let any
  anonymous visitor read/modify/mass-`unlink` every config session. Added 3
  protective `ir.rule`s scoping all four ops to the requester's own records
  (controllers sudo() their real work, so the storefront flow is unaffected;
  the rules only constrain direct RPC).
- **CRITICAL (data loss):** `remove_inactive_config_sessions` GC deleted
  `state='draft'` sessions with no bookmark/saved exclusion — a "Saved
  Configuration" stays draft and `session_id` is `ondelete=cascade`, so the
  buyer's saved bookmark vanished after 3 days. Now excludes
  `has_active_bookmark`/`is_saved` (and runs sudo()).
- **MEDIUM (DoS):** `safe_eval(custom_field_value)` on unauthenticated public
  POST text → strict `int()`/`float()` parsing (arbitrary-expression CPU
  exhaustion removed).
- **LOW:** parameterized the migration SQL.

### Verified clean (no change)
All v19 mechanical-port axes (JS `rpc` import / Interactions patch /
`type="jsonrpc"` / `_slug` / `t-out` / no `<tree>`/`attrs=`); CSRF; XSS; no open
redirect; the `_check_reconfigure_ownership` cookie-bound IDOR guard.

### Documented (not changed)
Cookie-bind the `cfg_session` render route for anonymous (route-level info-leak
remains); patch the base `_gc_draft_sessions` bookmark gap upstream; add
anonymous rate-limiting; verify the `base.group_public` implied_ids write lands.
See `REVIEW_REPORT.md`.
