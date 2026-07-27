# Code Review — `southbrook_os` (Module #12, Tier 2 — governed knowledge layer)

**Version:** 19.0.1.0.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Scope:** ~916 LOC — 5 models, 1 public controller, 1 RAG export, 11 canonical markdown docs, ir_cron, post_init_hook, 10 test files.
**Method:** Two independent parallel audits (v19-compat + code; security + performance), each cited to file:line; every CRITICAL/HIGH claim re-verified by me against source, seed frontmatter, and the call graph before editing. Distinct from `southbrook_os_kernel` (Module #1).

---

## Executive Summary

`southbrook_os` is the version-controlled "how Southbrook works" knowledge layer — canonical markdown + Odoo-generated sections, governed via OS Revision Orders (OSROs), published as dated snapshots, exported for Hermes RAG, and served on a **public** JSON endpoint. The v19-compat audit found the module **v19-clean** (every correct idiom present: `models.Constraint`, v19 cron schema, `post_init(env)`, `yaml.safe_load`, `@api.model_create_multi`, correct AbstractModel `env.get()` probing). The **security** picture was the opposite: the module's entire governance premise (audience-scoping + publish-gate) was **not enforced at the one place it mattered — the public controller**.

Fixed: **1 CRITICAL data-exposure, 1 HIGH unauthenticated-write, 1 MEDIUM latent-XSS, 1 MEDIUM idempotency gap, 2 LOW** — plus repaired the module's own pre-existing test-isolation bugs. Result: install + upgrade clean, **26/26 tests green (from a 2-failed/7-error baseline)**, with 2 new security regression tests. Three deeper items (governance "theatre", OSRO segregation-of-duties, snapshot retention) are documented as owner/design decisions.

---

## Original Issues Found

### Fixed

| # | Sev | Title | Root cause |
|---|-----|-------|-----------|
| F1 | **CRITICAL** (disclosure) | Public endpoint leaked the entire internal knowledge base | `controllers/os_public.py` `os_json` did `sudo().search([])` with **no filter** and dumped every section's `body`/`source`. The data declares an `audience:` policy the code ignored — **only `00_charter` is tagged `public`**; `20_systems_topology` (`[mfg_manager, overseer]`: container names, deploy paths, co-tenant list = infra recon), partner tiers, production control, PLM, and live generated catalog/work-center/cut-spec data were all served to anonymous `curl`. |
| F2 | **HIGH** (unauth write / DoS / TOCTOU) | Anonymous GET performed privileged DB writes | The `auth="public"` route called `Pub.publish()` under `sudo()`, which `create`s a publication + N snapshot rows. `publish()` was the **only** caller anywhere (cron ran `generate_all` which never published; OSRO approval never published) — so publications were built *exclusively* by anonymous traffic. Check-then-create with no lock races the `UNIQUE(calendar_key, build_hash)` constraint → uncaught `IntegrityError` → 500 to anonymous clients. |
| F3 | MEDIUM (latent stored XSS) | `body_html` computed with `sanitize=False` | `os_section.py` rendered markdown→HTML with the sanitizer off. Bodies flow in from generators that interpolate live product/work-center names; the moment `body_html` is placed in any view, that is stored XSS. |
| F4 | MEDIUM (idempotency) | Canonical re-load dropped frontmatter changes | `os_loader.py` update branch wrote only `body`/`name`, ignoring `source`/`audience_tags` and never bumping `version`. An `audience:` change in a canonical `.md` silently failed to propagate on re-load — and (compounding F1) a section could keep a stale, wrong audience tag. |
| F5 | LOW (py3.12 deprecation) | `datetime.datetime.utcnow()` | `exports/rag_corpus_export.py` used the deprecated naive-UTC call. |
| F6 | LOW (perf) | Missing index on `publication_id` | The O2m reverse lookup on `southbrook.os.publication.section` had no index. |

### Test-quality bugs fixed (the module's own tests, broken by its own post_init)

- 7 `UniqueViolation` errors: `test_os_publication`/`test_os_revision` `setUp` re-created canonical slugs (`00_charter`, `04_lifecycle`) that the post_init hook already loads → isolated the fixtures.
- `test_section_created` required `<h1>`, assuming the **optional** `markdown` package → made it tolerant of the documented fallback renderer.
- `test_cut_spec_generator` required `thickness`/`reveal`, which only exist when `southbrook_plm` provides `southbrook.cut.spec` → asserts the documented stub path when absent.

### Documented for owner/design decision (NOT auto-applied)

| # | Sev | Title | Why not auto-fixed |
|---|-----|-------|--------------------|
| D1 | HIGH (design) | Publish-gate is "theatre" — endpoint serves **live** section bodies, not the frozen `publication.section_snapshot_ids` | Once F1's audience filter is in place this is no longer an *exploit* (only public-tagged content is exposed), but an unpublished edit to a public section still goes live immediately. Serving from the snapshot requires adding `audience_tags` to the snapshot model + payload remap + test changes — a larger refactor best confirmed with the owner. Fix documented. |
| D2 | MEDIUM (policy) | OSRO has no segregation of duties | `action_approve`/`action_apply` don't check `user ∉ author`; `reviewer_ids` is decorative. Enforcing approver≠author would **block a solo-admin shop** (Southbrook is small) — a business-policy call. |
| D3 | MEDIUM (growth) | No publication/snapshot retention | Now that the cron publishes (F2 fix), a new full publication + N snapshot rows is written whenever content changes. Recommend a retention GC (keep latest per `calendar_key`, or last K). |
| D4 | LOW | RAG export loads all bodies in memory; `test_loader` hardcodes `/mnt/extra-addons/...` | Fine at current corpus scale; noted. |

---

## Repairs Completed

**F1 — audience filter** (`controllers/os_public.py`): `search([("audience_tags", "ilike", "public")], order="slug")` with a comment naming the internal docs and forbidding widening without re-auditing `canonical/*.md` tags.

**F2 — read-only endpoint + server-side build**:
- Controller now `search`es the latest **existing** publication (read-only, no create) and guards a `None` publication in the payload.
- `os_generators.generate_all` (the daily cron target) now calls `publish(month_key)` after regenerating — building moves to the authenticated cron context.
- `post_init` builds an initial publication so the endpoint has provenance from install.

**F3** — dropped `sanitize=False` on `body_html` (default sanitizer keeps the markdown-safe subset, strips scripts).

**F4** — loader update branch now writes `source`+`audience_tags` and `bump_version()`s when the body actually changed (mirrors `_upsert_generated`).

**F5** — `datetime.datetime.now(datetime.timezone.utc).isoformat()`.

**F6** — `index=True` on `publication_id`.

**Tests added:** `test_os_json_returns_only_public_sections` (asserts `00_charter` served, internal slugs NOT leaked, every served section is public-tagged) and `test_public_get_does_not_write_publications` (asserts read-only). Both pass on the fixed code and would fail on the vulnerable baseline.

---

## Files Changed
- `controllers/os_public.py` (audience filter + read-only)
- `models/os_generators.py` (+ `import datetime`; `generate_all` publishes)
- `__init__.py` (+ initial publish in post_init)
- `models/os_loader.py` (full-vals refresh + version bump)
- `models/os_section.py` (`sanitize=False` removed)
- `models/os_publication.py` (`publication_id` index)
- `exports/rag_corpus_export.py` (tz-aware UTC)
- `tests/{test_public_endpoint,test_os_publication,test_os_revision,test_os_section,test_generators}.py`
- `__manifest__.py` (version bump)

## Database Impact
- New index on `southbrook_os_publication_section.publication_id` (additive).
- Publications are now built by cron/post_init instead of anonymous traffic — same rows, authenticated context. No schema/migration; no field type changes (removing `sanitize=False` doesn't alter the column).

## Security Improvements
- Anonymous internet disclosure of infra topology + internal knowledge base closed (F1).
- Unauthenticated writes + TOCTOU-500 on the public route eliminated (F2).
- Latent markdown→HTML stored-XSS sink removed (F3).
- Residual (documented): D1 (live-vs-snapshot), D2 (OSRO SoD).

## Performance Improvements
- Public GET no longer triggers a build-and-write on cache-miss (F2). `publication_id` indexed (F6).

## Remaining Risks
- **D3 retention**: unbounded publication growth is now driven by the cron; add a GC before heavy use.
- **D1**: edits to *public* sections go live pre-publish; low blast radius (only the charter is public today) but worth closing if the public surface widens.

## Recommendations (priority)
1. **D1** — serve `publication.section_snapshot_ids` (add `audience_tags` to the snapshot) to make the publish-gate real.
2. **D3** — retention GC cron.
3. **D2** — decide OSRO segregation-of-duties policy (blocks solo-admin if enforced).
4. Declare `markdown` intent: either add it to `external_dependencies` (if prod requires rich rendering) or keep the fallback as the supported path.
