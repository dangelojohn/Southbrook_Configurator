# CHANGELOG — `southbrook_os`

## 19.0.2.0.0 — 2026-07-11 — Code-review pass (Module #12)

### Security
- **[CRITICAL] Public endpoint no longer leaks internal sections.** `/southbrook/os.json`
  now serves only sections whose canonical `audience:` frontmatter includes `public`
  (today: `00_charter`). Previously `search([])` dumped every section — systems
  topology (container names, deploy paths, co-tenant list), partner tiers,
  production control, PLM, and live generated data — to anonymous callers.
  `controllers/os_public.py`.
- **[HIGH] Public route is now read-only.** It reads the latest existing publication
  for provenance metadata instead of calling `publish()` (which created rows under
  `sudo()` on an anonymous GET, with a TOCTOU race on `UNIQUE(calendar_key,
  build_hash)` → 500). Publication building moved to the daily cron
  (`os_generators.generate_all`) and an initial build in `post_init`.
  `controllers/os_public.py`, `models/os_generators.py`, `__init__.py`.
- **[MEDIUM] Removed `sanitize=False` on `southbrook.os.section.body_html`** —
  markdown→HTML is now sanitised (latent stored-XSS sink). `models/os_section.py`.

### Fixed
- **[MEDIUM] Canonical re-load is now fully idempotent.** The loader update branch
  writes `source` and `audience_tags` (not just `body`/`name`) and bumps `version`
  when the body changes, so frontmatter edits propagate on re-load.
  `models/os_loader.py`.
- **[LOW] `datetime.utcnow()` → `datetime.now(timezone.utc)`** (py3.12 deprecation).
  `exports/rag_corpus_export.py`.
- **[LOW] Added `index=True` on `southbrook.os.publication.section.publication_id`.**
  `models/os_publication.py`.

### Tests
- Added `test_os_json_returns_only_public_sections` (leak regression guard) and
  `test_public_get_does_not_write_publications` (read-only guard).
- Fixed pre-existing test-isolation bugs: isolated `test_os_publication` /
  `test_os_revision` `setUp` from post_init canonical slugs; made the markdown
  header assertion tolerant of the optional `markdown` package; made the cut-spec
  test assert the documented stub when `southbrook_plm` is absent.
- Result: **26/26 green** (was 2 failed / 7 error at baseline).

### Notes (unchanged by design — owner/design decisions)
- Public endpoint still serves LIVE section bodies, not the frozen publication
  snapshot (governance "theatre") — documented as HIGH design rec (D1).
- No OSRO segregation-of-duties enforced (would block a solo-admin shop) — D2.
- No publication retention GC yet (now more relevant since the cron publishes) — D3.
