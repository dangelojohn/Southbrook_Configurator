# Code Review & Repair Report — `southbrook_os_kernel`

**Module:** Southbrook OS Kernel · **Version:** 19.0.1.0.0 → **19.0.1.1.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 Community Edition
**Queue position:** #1 of 46 (Tier 0 — foundational leaf, depends only on `base`, `mail`)
**Review method:** 3 parallel read-only audit agents (v19-compat/code, security, performance), each finding independently verified against source and against the v19 core in the local `v19c-odoo` container before any repair was applied.

---

## Executive Summary

The OS Kernel is the platform's AI operating-system layer: a never-raises AI routing kernel (`southbrook.os.ai.kernel`), a kill-switch registry, an AI request ledger, a namespaced shared-memory store, an agent registry with daily budgets, and a tool registry. It "ships dark" (master AI switch seeded disabled) and no feature has been migrated onto it yet.

**The module was found to be of exceptionally high quality and is fully v19-CE compatible.** It is clean on all 11 known v19-breakage axes (verified, not assumed): it correctly uses `models.Constraint` (not the silently-ignored `_sql_constraints`), the `res.groups.privilege` category mechanism, `@api.model_create_multi`, the `_name in env` membership guard against the AbstractModel-falsy trap, `<list>` (not `<tree>`) views, `self.env.company`, and parameterized SQL. **Zero correctness defects and zero deprecated-API usages were found.**

All repairs applied are **operational hardening and test-coverage**, not bug fixes — with one exception (a latent provenance defect in the ledger). Every change is additive and low-risk. The most material finding was that the AI request ledger had **no retention policy** and would grow unbounded by design.

**Severity tally:** 0 Critical-correctness · 0 High-correctness · 1 Critical-operational (ledger retention) · 2 High-perf (indexes) · 2 Medium (multi-company rule, ledger provenance) · plus test-coverage gap. All fixed.

---

## Original Issues Found

| # | Severity | Axis | Finding |
|---|----------|------|---------|
| R1 | **Critical (operational)** | Performance | `southbrook.os.ai.request` ledger — one row per kernel call, up to ~4KB each — had **no pruning/retention** cron or method. Unbounded monotonic table growth was a certainty by design (`os_ai_request.py`, `data/ir_cron.xml` defined only memory-vacuum + budget-reset crons). |
| R-prov | **Medium (correctness)** | Code | Ledger rows are created via `sudo()` (to bypass the admin-only create ACL). The `user_id` field default `lambda self: self.env.user` therefore resolved to **SUPERUSER/OdooBot on every row**, silently defeating the per-user cost/usage attribution the field exists for (`os_ai_kernel.py:_safe_log`). |
| R2a | **High** | Performance | `os_ai_request.user_id` (Many2one) had no index, but the "My Requests" search filter (`domain=[('user_id','=',uid)]`) scans it — Postgres does not auto-index FK columns. Full scan of the high-volume ledger on every use. |
| R2b | **High** | Performance | `os_ai_request` `_order = "create_date desc"` + a `create_date` group-by both hit the never-indexed magic `create_date` column — full sort/scan on every default list load. |
| R2c | **Medium** | Performance | `os_memory.expires_at` scanned in full by the daily `vacuum_expired` cron; not indexed. |
| R3 | **Medium** | Security | `os_ai_request` carries a `company_id` but shipped with **no `ir.rule`** — in a multi-company deployment an OS Viewer in company A could read company B's full prompt/response ledger. No record rules existed at all in the module. |
| R4 | **Medium** | Testing | The four `models.Constraint` uniqueness rules (the single riskiest v19-migration pattern here) were **never directly tested** — existing tests only prove the search-then-upsert helpers avoid duplicates, so a typo in a constraint's SQL (wrong column) would ship silently. |

### Reviewed and found clean (no action)
- **v19 compatibility:** all 11 breakage axes clean (constraints, groups/privilege, ir.cron schema, AbstractModel, `@api.depends`, view validation, decorators, ACL refs, manifest load-order). Verified against core source.
- **SQL injection:** the one raw `cr.execute` (`os_agent._lock_row`) is fully parameterized. Clean.
- **Controllers:** none exist; the tool-registry seed rows are metadata describing *other* modules' routes.
- **Kill-switch write ACL:** correctly locked to `group_os_admin` only; regular employees get zero access.
- **eval/exec, mutable defaults, manual `commit()`:** none.

---

## Repairs Completed

1. **R1 — Ledger retention (`autovacuum`).** Added `SouthbrookOsAiRequest.autovacuum()`: chunked (1000-row) deletion of rows older than `os.ai.ledger_retention_days` (config param, default **90**; `<= 0` = keep forever / opt-out). Wired to a new daily cron `ir_cron_os_kernel_prune_ledger`, mirroring the module's existing `vacuum_expired` pattern. Never raises.
2. **R-prov — Ledger provenance.** `_safe_log` now sets `vals["user_id"] = self.env.uid` (the real caller, captured before the `sudo()` create) so attribution survives the privilege elevation.
3. **R2a/b/c — Indexes.** `index=True` added to `os_ai_request.user_id`, an indexed `create_date` override on `os_ai_request`, and `index=True` on `os_memory.expires_at`.
4. **R3 — Multi-company rule.** New `security/ir_rule.xml` with a global `ir.rule` scoping the ledger by `company_id` (standard `['|',('company_id','=',False),('company_id','in',company_ids)]`); no-op in single-company. Added to manifest after the access CSV.
5. **R4 — Constraint tests.** New `tests/test_constraints.py` — forces a genuine duplicate `create()` per constraint (switch.key, memory namespace+key, agent.code, tool.code) and asserts `IntegrityError`; plus a positive test that same-key/different-namespace is allowed. New `tests/test_ledger.py` — provenance (user_id is the real caller, never SUPERUSER) and retention (prunes past-retention rows, honours the `<= 0` opt-out).
6. Manifest version bumped `19.0.1.0.0 → 19.0.1.1.0` to trigger the upgrade.

### Deliberately NOT changed (respecting "don't rewrite working code")
- **`ormcache` on `os_switch.is_on()`** (perf agent's suggestion): declined. The benefit is marginal (two `limit=1` lookups on an indexed unique column, negligible against a 0.5–2 s LLM round-trip), and adding cross-worker cache invalidation to a kill-switch reintroduces exactly the ormcache-coherency wedge class this codebase has been bitten by. Documented as an optional future optimization gated on real call volume.
- **Rewriting the stored `name` post-create UPDATE:** the author documented this as a deliberate trade-off; the cost is a primary-key-keyed UPDATE on a now-retention-bounded table (immaterial), and the N+1 shape only triggers on batch creates the kernel never issues. Left as-is.
- **Removing the redundant single-column indexes** on `os_memory.namespace`/`key`: harmless; removal changes schema for no real-world gain.

---

## Files Changed

| File | Change |
|------|--------|
| `models/os_ai_request.py` | `create_date`/`user_id` indexes; `autovacuum()` retention method; retention constants |
| `models/os_ai_kernel.py` | `_safe_log` stamps real `user_id` before sudo create |
| `data/ir_cron.xml` | new `ir_cron_os_kernel_prune_ledger` daily cron |
| `security/ir_rule.xml` | **new** — multi-company rule on the ledger |
| `__manifest__.py` | register `security/ir_rule.xml`; version → 19.0.1.1.0 |
| `tests/test_constraints.py` | **new** — 5 constraint-enforcement tests |
| `tests/test_ledger.py` | **new** — 3 provenance + retention tests |
| `tests/__init__.py` | register the two new test modules |

No existing model logic, field semantics, or public method signatures were changed. Business behavior is preserved.

---

## Database Impact

- **New indexes** (created on module upgrade): `southbrook_os_ai_request.user_id`, `southbrook_os_ai_request.create_date`, `southbrook_os_memory.expires_at`. The ledger table currently ships empty (dark), so index creation is instantaneous; on an already-populated instance it is a brief, safe `CREATE INDEX`.
- **New cron record** `ir_cron_os_kernel_prune_ledger` (daily). `noupdate="1"` data, so an admin's later edits survive upgrades.
- **New `ir.rule`** (global) on the ledger — tightens visibility only; cannot expose new data.
- **New config param** `os.ai.ledger_retention_days` (created lazily on first cron run; default 90 when unset).
- No column drops, no type changes, no data migration required. Fully forward-compatible; downgrade would simply leave the extra indexes/cron/rule in place harmlessly.

---

## Security Improvements

- **Multi-company data isolation** on the AI request ledger (R3) — closes cross-company prompt/response read exposure for OS Viewers.
- **Restored per-user attribution** (R-prov) — the ledger now truthfully records who initiated each AI call instead of attributing everything to OdooBot, which is a prerequisite for any per-user cost/abuse auditing built on top.
- Confirmed (no change needed): kill-switch writes remain admin-only; no SQL injection; no eval/exec; no HTTP surface; API-key handling and error-logging hygiene (never echoing prompt/response bodies) are sound.

---

## Performance Improvements

- **Bounded ledger growth** (R1) — the single highest-impact change; converts an unbounded-bloat table into a retention-capped one.
- **Three indexes** (R2) eliminate full scans on: the "My Requests" filter, the default `create_date desc` list order + date group-by, and the daily memory-vacuum scan.

---

## Testing Results

_See `TEST_RESULTS.md` for the full run log._ Validated on the local `v19c-odoo` (Odoo 19 CE) container against an isolated throwaway DB — prod untouched:
- **Cold install:** PASS (fresh DB, module + 26 deps).
- **Upgrade** 19.0.1.0.0 → 19.0.1.1.0: PASS (indexes/cron/rule migrated cleanly).
- **Automated tests:** **53 tests, 0 failed, 0 errors** (incl. the 8 added by this review).
- **DB evidence:** all 3 indexes, the prune cron, and the multi-company rule confirmed present.

The provenance test initially failed because Odoo's `TransactionCase` runs as SUPERUSER; the *fix* was correct, the *test* was corrected to drive `run()` as a real non-superuser (`with_user`). Notably, live-DB verification also caught that the `os_memory.expires_at` index hadn't actually applied on the first pass — it was applied and re-verified.

---

## Remaining Risks

1. **Preview redaction (design, not a bug).** `prompt_preview`/`response_preview` store the first 2000 chars unredacted. Harmless today (no feature routes real data through the dark kernel yet), but before the first feature is migrated onto `kernel.run()`, a scrub/redaction hook should be added and a policy set — this is the moment, before the blast radius grows. Documented, not code-changed (out of scope for "repair existing behavior").
2. **`remember()` caller contract.** `os_memory.remember()` does a `sudo()` write keyed on caller-supplied `namespace`/`key` with no size cap. Not exploitable within this module (no controllers), but any future controller forwarding raw user input into it would get a privileged unbounded write. Should be stated as a caller contract in `OS_KERNEL_SPEC.md` and optionally capped.
3. **`os_switch` viewer-via-RPC.** An OS *Viewer* (read-only) could invoke the `set_switch` helper over RPC to flip a switch, since the helper `sudo()`-writes. Low severity (Viewers are semi-trusted; regular employees have no access at all; the helper has no runtime callers outside tests). Left unchanged to avoid over-fitting; noted for the owner.

---

## Recommendations

- **Optional perf (future):** cache `is_on()` via `ormcache` *only* once real per-call volume materializes, with correct CRUD invalidation — weigh against this repo's history of ormcache-coherency wedges.
- **Before first feature migration:** add the preview redaction hook (Risk 1) and document the `remember()` caller contract (Risk 2).
- **Confirm** `"application": True` is intended (it surfaces the kernel as an App tile) — likely deliberate for the top-level menu.
- **Set `os.ai.ledger_retention_days`** explicitly per the deployment's compliance/retention needs (default 90 is a reasonable start).
