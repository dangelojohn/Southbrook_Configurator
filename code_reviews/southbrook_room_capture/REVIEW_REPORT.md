# Code Review — `southbrook_room_capture`

**Module #25 of 46 · Odoo 19.0 CE**
**Version:** 19.0.3.0.1 → **19.0.3.1.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (v19+JS compatibility; security+performance) →
independent source verification → minimal real fixes + regression tests → live
`-i` + `-u` + tests on isolated DB (`ci_room_capture`, full southbrook dep stack
staged).

---

## What the module does

AI-assisted room-geometry estimation. `southbrook.room.capture` (an
**AbstractModel**, `analyze()`) accepts 1–5 room photos, downscales them in
memory, calls the Anthropic Messages API (vision), and returns a **normalized,
defensively-clamped** geometry estimate. It also ships the QR-scan pieces
(`southbrook.qr.part` / `.qr.staff`) that let a portal customer / internal staffer
resolve a scanned production-package QR to its safe serialized view. Two OWL
front-ends: a public `RoomSetupWizard` patch (AI pre-fill) and a staff scanner
(`public_components` mount).

**Critical safety property (verified):** the AI response is *never* persisted and
*never* writes production geometry. `analyze()` returns a suggestion; the only
persistence path is the existing human-gated `RoomSetupWizard`, which routes every
save through `southbrook.room.validate_geometry`. No `ir.attachment`, no disk, no
image bytes logged.

---

## Verdict

**Unusually well-defended. No CRITICAL, no install- or web-client-breaking
issue.** Both audits and live validation agree. One concrete cost-abuse
mitigation applied; the two systemic HIGHs need infra/architecture decisions and
are documented below.

---

## Findings

### Fixed

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| F1 | LOW→v19 | 3 JSON-RPC routes + docstring used the deprecated `type="json"` alias | → `type="jsonrpc"` (`controllers/main.py:12,208,363,465`). Committed to the working tree (deploys rsync the tree — see `southbrook_deploy_stale_tree_hazard`). |
| F2 | HIGH (mitigation) | **Paid-API cost abuse.** The controller rate limiter (`_RATE_BUCKETS`, `main.py:74`) is **per-worker** — effective ceiling is `W × 20/hr/user`, and portal self-signup lets an attacker mint fresh users. No cross-worker or global spend ceiling → an unbounded Anthropic bill. | Added a **global daily call cap + kill-switch** shared by all workers: `_room_capture_consume_daily_quota()` gates every real (non-mock) `analyze()` before `_call_anthropic`. `ir.config_parameter southbrook_room_capture.max_daily_calls` (default **500**); **0 = hard kill-switch** (no real call ever). Mirrors the `southbrook_agent_gateway` #24 mitigation. +3 regression tests. |

### Documented (need owner / infra decision — not unilaterally changed)

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| R1 | HIGH | **Per-worker rate limiter has no shared state.** `_RATE_BUCKETS = {}` (`main.py:74`) is process-local; N workers → N× the intended limit, and it resets on worker recycle. The daily cap (F2) bounds *total spend* but not *per-user fairness* across workers. | Back the limiter with a shared store (Redis, or a small `ir.config_parameter`/DB-row counter keyed by user+window). Same class as `southbrook_ai_design` #21 R1. |
| R2 | HIGH (perf) | **60 s synchronous Anthropic call blocks the worker.** `_call_anthropic` → `httpx.post(..., timeout=60.0)` (`models/…:466`) holds the HTTP worker for up to a minute; a handful of concurrent captures can starve the pool (availability DoS). | Offload to an async job (OCA `queue_job`, or a cron-drained request row) and have the front-end poll. Same class as `southbrook_ai_design` #21 R2. |
| R3 | MEDIUM | **Portal-triggerable auto-lead.** A trustworthy capture auto-creates a `crm.lead` (`main.py:346`). Bounded (idempotent per order) but portal-reachable → CRM noise if abused. | Gate behind the F2 quota (already partly covered) or defer lead creation until the human wizard save. |
| R4 | LOW | **Signed-QR TTL not enforced.** The QR payload carries a timestamp but the resolve path ignores it (`southbrook_qr_part.py:94`). Ownership is the real boundary (double-checked), so impact is defense-in-depth only; enforcing TTL could break legitimate re-scans of older labels. | Optional: enforce a generous TTL (e.g. 1 yr) if label re-issue is acceptable. |
| R5 | LOW | **Base64 decoded before the size cap.** `_decode_image_item` (`main.py:279` path) decodes then checks `_MAX_IMAGE_BYTES`; a hostile payload allocates the decoded buffer first. Body size is already bounded upstream, so impact is marginal. | Optional: reject on encoded length (`len × 3/4`) before `b64decode`. |

---

## Strong positives (verified against source)

- **AI output never corrupts production geometry** — returned to the human-gated
  wizard only; `_normalize_estimate` clamps every field (`…:571-652`).
- **QR IDOR closed** — double ownership check, no existence oracle
  (`main.py:388-430`).
- **API key hygiene** — sudo-only read, no shipped secret, `use_mock=True`
  default, key never logged (error path logs `resp.status_code` only, `…:474`);
  header auth (`x-api-key`), not URL.
- **No `eval` / no `t-raw` / no XSS**; HMAC compares are constant-time
  (`southbrook_qr_kit`); PII photos never persisted or logged.
- **Install-safety** — header-only ACL CSV (all AbstractModels), lazy `httpx`/PIL
  imports, `utm_data.xml` uses no `<function>`/`obj()` trap, all cross-module
  fields resolve, `env.ref(..., raise_if_not_found=False)` guards.
- **v19 JS correct** — `rpc` from `@web/core/network/rpc`, `public_components`
  mount (no double `startServices`), valid `patch()`/`t-inherit` targets, jsQR ESM
  shim, no forbidden OWL tokens.

---

## Validation

- `-i southbrook_room_capture` (full dep stack) — **clean install**, registry
  loaded 37.3 s.
- `-u southbrook_room_capture` — **clean upgrade**, idempotent.
- Tests `--test-tags=southbrook_room_capture` — **46/46 pass, 0 failed, 0 errors**
  (incl. 3 new daily-cap tests). See `TEST_RESULTS.md`.

## Env note

The OrbStack test VM exhibited a transient TIME_WAIT storm (all ~28 k ephemeral
ports briefly in `TIME_WAIT`, `EADDRNOTAVAIL` on new TCP) that blocked
`createdb`/odoo DB connects. Worked around by creating the DB via the db
container's **local unix socket** (`docker exec v19c-db createdb …`) and running
the test once the pool drained (`tw=0`). Not a module issue.
