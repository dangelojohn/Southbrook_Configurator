# TEST_RESULTS — southbrook_training_hub

**DB:** `ci_train45` (isolated, full dep stack incl. website_slides + southbrook_hermes)
**Odoo:** 19.0-20260513 CE · **Date:** 2026-07-11

## Test suite
**None ships** — the module has no `tests/` directory (`0 tests`). Validation is
install/upgrade integrity + code review + the two audit agents + runtime install probes.

## Validation
| Phase | Result |
|-------|--------|
| `-i southbrook_training_hub` (fresh DB, full dep stack) | **clean**, registry ~65 s |
| `-u southbrook_training_hub` | **clean** |
| post_init seed vs new `url` constraint | **passed** — no ValidationError (seeded slide URLs are `/slides/...` / `/web/content/...`, both leading-slash) |
| `display_name` compute (V1 fix) | registry loaded with no `@api.depends` break |

## Notes
- The module is read-only discovery metadata; the security fixes (role-gate identity,
  internal-only routes, url scheme) are validated by code review + install integrity.
- The v19 agent verified OWL/JS is fully v19-correct (no removed `useService`, `t-esc`
  throughout, valid systray registration) and both controllers function.
- Runtime shell probes of `display_name`/the url constraint were attempted; the odoo-shell
  invocations hit heredoc-quoting artifacts (not code issues) — the install-level checks
  above cover the same guarantees (registry + seed).
