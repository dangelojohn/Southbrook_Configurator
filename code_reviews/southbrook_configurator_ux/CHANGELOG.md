# CHANGELOG — `southbrook_configurator_ux`

## 19.0.1.8.0 — 2026-07-11 — Code-review pass (Module #17)

### Security
- **[HIGH] Anonymous config sessions are now isolated by HTTP session, not the
  shared public_user id.** `_get_or_create_session` scopes anon sessions to
  `request.session["sb_ux_config_session_ids"]`; `_authorize_session` verifies a
  public session belongs to THIS HTTP session. Previously every anonymous
  visitor was `base.public_user`, so two shoppers collided on one draft session
  and any anon could read/mutate any other anon's config via a crafted
  `session_id`. Authenticated users keep the `user_id` binding.
  `controllers/main.py`.

### Changed (v19)
- **`type="json"` → `type="jsonrpc"`** on `/state`, `/select`, `/commit`
  (deprecated alias). `controllers/main.py`.

### Tests
- Added `test_anon_sessions_isolated_by_http_session` (two-visitor IDOR
  regression) — passes on the fix, would fail on the old user_id-only check.

### Notes
- Pricing is server-side (money vector already closed) — verified, unchanged.
- `/select` template-membership value validation was attempted but reverted: the
  naive `tmpl.attribute_line_ids` allowed-set rejected legitimate picks (OCA
  session exposes SKU attributes differently). Documented as D1.
- **Pre-existing (not a regression): 15 `test_select_commit` failures** on the
  current v19 CE build — SKU `-XXX` composition + `incomplete_configuration` for
  required attributes the module's own seed adds but the test fixtures predate.
  Confirmed identical on unmodified HEAD. Recommend a dedicated fixture pass.
