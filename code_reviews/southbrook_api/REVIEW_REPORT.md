# Code Review — `southbrook_api`

**Module #28 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.1.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+perf; v19+contract) → independent
source verification → minimal real fixes + regression tests → live `-i` + `-u` +
tests on isolated DB (`ci_api`, full southbrook dep stack staged).

---

## What the module does

Stateless REST API (`/api/v1/*`, the "G6 contract") consumed by a Flutter mobile
app: API-key auth (hashed keys), idempotency-key replay safety, and endpoints for
kitchen projects, photo upload → AI analysis, design concepts, approvals, and the
Accucutt cut-list nesting bridge.

---

## Verdict

Well-architected on the core security surface — but one **HIGH privilege-escalation**
(a one-line ACL error) and several correctness/hardening gaps. All fixed. The
v19+contract audit found the module **cold-installs and upgrades cleanly** with all
cross-module references verified to source; routes are `type="http"` (no
json→jsonrpc migration needed) and use the v19-safe JSON body accessor.

---

## Findings

### Fixed — security

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **F1** | **HIGH** | **API-key forgery → privilege escalation.** `ir.model.access.csv` granted `base.group_user` **create+write** on `southbrook.api.key` with **no record rule**. `verify()` trusts `key_hash → user_id`, and `requires_api_key` does `update_env(user=user.id)`. So any employee could `create({"user_id": <admin>, "key_hash": sha256("secret")})` via RPC and then call any `/api/v1/*` route with `X-Api-Key: secret` **as admin** (the hash algo is in the shipped source). The same write grant also allowed fleet-wide key revocation (DoS). | ACL → **read-only** for `group_user`; added an `ir.rule` `[('user_id','=',user.id)]` (own keys only); `action_revoke` now checks ownership and writes under sudo (group_user has no write). Issuance/verification always ran via sudo methods, so no user needs create/write. +2 regression tests. |

### Fixed — correctness / operational

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **F2/F3** | MEDIUM | **Idempotency `stash` create had no savepoint.** Under the exact scenario idempotency exists for — two concurrent requests with the same `Idempotency-Key` — the second `create` hits `UNIQUE(...)`; catching that `IntegrityError` **without a savepoint** leaves the PG transaction aborted ("poisoned cursor"), so the request's `COMMIT` fails: the client gets a **500 and the handler's real work rolls back** — the opposite of idempotent. | Wrapped the `create` in `with self.env.cr.savepoint():` so the violation rolls back only the reservation. |
| **F4** | MEDIUM | **Promised GC cron never shipped.** The model docstring claims a cron trims expired idempotency rows, but there was **no `ir.cron`** — the table grows one row per POST forever (the lazy unlink in `get_cached` only trims replayed rows). | Added `_gc_expired()` (batched, test-safe commit) + a daily `ir.cron` (v19 schema — no `numbercall`/`doall`). |
| **F6** | MEDIUM | **No cost cap on the paid AI path.** `POST .../photos` triggers `analyze_photo` (a paid AI call) with no per-day cap or kill-switch — a valid key (or, absent F1, a forged one) could drive unbounded spend. | Added a **global daily cap + kill-switch** (`ir.config_parameter southbrook_api.max_daily_analyses`, default 500; 0 = kill-switch), checked before the analysis. Mirrors `southbrook_room_capture`/`_room_chat`. |
| **F8** | LOW | `_fetch_project_or_404` used `project.partner_id != partner`; if BOTH are empty, `empty != empty` is False → a partnerless user could read partnerless projects. | Explicit `not partner or project.partner_id != partner` guard. |
| **F9** | LOW | `/api/v1/health` (unauthenticated) returned `request.env.cr.dbname` — leaks the DB name (aids dbfilter/db-manager targeting). | Dropped the `db` field. Test updated to assert its absence. |
| — | — | **Pre-existing test drift**: `test_cutlist_nesting` asserted `southbrook.nesting.v1`, but `to_nesting_envelope()` (in `southbrook_kitchen_mrp`) now emits **v2** (input still accepts both). | Updated the test constant to `v2`. |

### Documented (business-policy / infra — not unilaterally changed)

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| F2/F3 (deeper) | MEDIUM | The savepoint fix stops the 500/rollback, but **double-execution still occurs** (both concurrent requests run the handler), and a **replay with a different body silently returns the first response** (body is neither in the cache key nor compared). | Full RFC-style idempotency: reserve the key (with a request-body hash) BEFORE running the handler; on a duplicate return the cached response if the body hash matches, else **422**; on an in-flight reservation return **409**. Needs a `body_hash` field + a decorator rework and a 409/422-semantics decision. |
| F5 | LOW | Login user-enumeration timing: `auth_login` pre-searches the user before the KDF. The redundant pre-search is removable, but the residual timing oracle is **inherent to Odoo CE `_login`** (fast-fails unknown logins). | Low value; the v19 audit rated it no-action. Left as-is. |
| F6 (login) | MEDIUM | `/auth/login` has no brute-force throttle (CE has no default per-account lockout). | Needs a shared-store rate limiter (same class as `southbrook_ai_design`/`_room_capture` R1). |
| F7 | MEDIUM | `/auth/login` mints a fresh 90-day key every call and never revokes prior ones → credential sprawl + key-table growth. | Cap active keys per user, or reuse/rotate. Business-policy decision. |

---

## Strong positives (verified)

- **Key model**: `secrets.token_hex(32)` (256-bit); only the SHA-256 **hash** is
  stored (cleartext shown once, never logged); hash-lookup verification is
  timing-safe by preimage resistance (no `compare_digest` needed); expiry +
  revocation enforced on every request.
- **Auth**: key read from `X-Api-Key` **header** (not URL); `requires_api_key`
  runs endpoints **as the key's user** (`update_env`), not blanket sudo — surgical
  sudo is paired with explicit ownership checks (`_fetch_project_or_404`) or
  record-rule enforcement (`_fetch_cutlist_or_404`, collapse-to-404, no existence
  leak).
- **Idempotency** cache is scoped by `api_key_hash` (+ route), so user A cannot
  read user B's cached response.
- **No mass-assignment** (`from_nesting_result` uses a type-checked allowlist), no
  `eval`, no client-supplied `domain`/`fields`, no SQL string-building; upload has
  a 7 MB cap + mime + PIL-decode check; CORS sets no credentials (header auth ⇒
  CSRF-safe).
- **v19-clean**: `models.Constraint`, v19-safe `request.httprequest.data` JSON
  body, all cross-module fields/methods traced to source.

---

## Validation

- `-i southbrook_api` (fresh DB) — **clean install**, registry ~31 s.
- `-u southbrook_api` — **clean upgrade**; new `ir.cron` + `ir.rule` installed;
  `group_user` ACL confirmed read-only (`1,0,0,0`) in DB.
- Tests `--test-tags=/southbrook_api` — **35/35 pass, 0 failed, 0 errors** (incl.
  2 new F1 regression tests). See `TEST_RESULTS.md`.
