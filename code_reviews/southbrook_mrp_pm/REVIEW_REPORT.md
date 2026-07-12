# Code Review — `southbrook_mrp_pm`

**Module #27 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.12.4 → **19.0.1.13.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+perf; v19+data) → independent source
verification → HEAD baseline → minimal real fixes + regression tests → live `-i` +
`-u` + tests on isolated DB (`ci_mrp_pm`, full southbrook dep stack staged).

---

## What the module does

Production management / shop-floor layer (6.8 kLOC). Adds a **production-approval
hard gate** on `sale.order` (Request → Approve/Reject → force-release bypass),
enforced at MO creation; a **shop-floor kiosk + Floor-Manager portal**
(`controllers/floor.py`) for the WO queue and single-tap start/finish; a
**shop-daily** planning engine; workcenter/equipment KPIs; and heavy routing /
workcenter / equipment seed data.

---

## Verdict

The module is **v19-clean** (the v19+data audit found zero install/web/correctness
defects — it is already hardened against every known v19 trap). But the security
audit surfaced **two real HIGHs** in the governance layer, both fixed. The module
was also substantially **pre-broken on the current (newer-than-prod) v19c build**:
7 of its own tests failed at baseline — all now repaired.

---

## Findings

### Fixed — security

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **F1** | **HIGH** | **Approval-gate state-laundering.** `production_approval_state` had no `groups=` and there was **no `write()` override**, so any user with write access to their own order (e.g. `group_sale_salesman`) could `write({"production_approval_state": "approved"})` or `write({"force_production_release": True})` via `call_kw`/XML-RPC and satisfy the MO-create gate with no independent approver — the exact kitchen_workspace/plm laundering pattern. The view buttons are gated, but views don't constrain RPC. | Added a **value-aware `write()` guard** on `sale.order`: a non-approver can't set state to `approved`, a non-manager can't set `force_production_release` (superuser/sudo exempt so the guarded actions + internal flows still work). |
| **F1b** | HIGH | `action_approve_production` (which RELEASES production) had no in-method group check — only the view button was gated, so a non-approver could self-approve via `call_kw`. | Added an explicit **Production-Approver** group check in the method body. |
| **F2** | **HIGH** | **Order Builder `send_to_production` exposed a sudo MO-creation path to portal (share) users.** The parent's `send_to_manufacturing` was hardened (2026-07-11) to reject `user.share` + honour the approval gate; this module's `send_to_production` override (`order_builder.py`) did **neither** — `order.with_user(user).sudo().action_send_to_production()` runs as OdooBot, and `_southbrook_resolve_order` grants share dealers/customers access to their own order. A portal dealer could self-serve the staff-only shop-floor release of an approved order. Only `UserError` was caught, so an `AccessError` escaped as a 500. | Reject `request.env.user.share`, check `production_approval_state` (defense-in-depth), and catch `AccessError` → clean `forbidden`. Mirrors the parent guard. |

### Fixed — audit trail

| # | Finding | Fix |
|---|---------|-----|
| Bypass audit | The manager `force_production_release` bypass was **unlogged** at the real (MO-create) gate — the only bypass audit lived in the now-dead `_check_production_approval_gate`. | Added `message_post` on the source SO (once per order) when the MO-create gate is bypassed. |

### Fixed — pre-existing test failures (baseline 7 → 0)

| Test | Was | Root cause & fix |
|------|-----|------------------|
| `test_so_blocked_without_approval` | FAIL | Tested the **abandoned** gate-at-`action_confirm` design (removed to break an approve↔confirm deadlock; gate moved to MO-create). Rewritten to assert confirm succeeds and `action_send_to_production` raises. |
| `test_so_bypass_with_manager_flag` | FAIL | Expected bypass chatter that only the dead gate produced. Rewritten to drive the real MO-create gate and assert the new bypass audit. |
| `test_30/40_..._action_shape` (w051) | ERROR | **Test bug**: `{tuple(t) for t in domain}` can't hash an `in`-operator leaf (list value) → "unhashable type: list". Changed set→list. |
| `test_route_registered` (w056) | FAIL | **v19 API drift**: `@http.route` stores metadata on `.original_routing` in v19, not `.routing` (even known-good routes have no `.routing`). Check both. |
| `test_old_done_activity_purged` (w057) | FAIL | `date_done` is a **stored computed** field (`@api.depends('active')`); the test's SQL-backdate was discarded by a recompute on `invalidate`. Added `flush_recordset()` so the value persists. (Also fixed the F4 commit — see below.) |
| `test_at_risk_when_mi_blocked_within_window` (w019) | FAIL | **Cross-module artifact**: needs `x_mi_status` from `southbrook_manufacturing_intelligence` (not a dep). The `if field in _fields` guard silently skipped the setup yet still asserted. Now `skipTest` when MI is absent. |

+3 new regression tests: `test_state_laundering_blocked_for_non_approver`,
`test_force_release_self_grant_blocked_for_non_manager`,
`test_approve_action_requires_approver_group`.

### Fixed — operational safety

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **F4** | MEDIUM | **Unbounded single-transaction `unlink()`** in the activity-retention cron — the module's own docstring says the table balloons past 10M+ rows; the first run would load the whole backlog into memory and delete it in one locked transaction (OOM / replication lag / rollback-wedge). | Batched delete (1000/chunk), committing between batches to bound memory + transaction/lock size. Commit skipped under `--test-enable` (v19 TestCursor forbids commit). |

### Documented (access-model / infra — not unilaterally changed)

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| F3 | MEDIUM | **Floor kiosk has no per-station authorization.** The POST handlers (`.../wo/<id>/start|finish`, `.../equipment/<id>/condition`) `browse(id).sudo()` and mutate with no check that the WO/equipment belongs to the operator's station — any floor-group member can advance/complete **any** WO or set **any** equipment's condition shop-wide (horizontal IDOR), and they write `state` directly (bypassing `button_start/finish` validation). Trust boundary is "all floor staff," so MEDIUM. | Add an operator→workcenter authorization mapping (doesn't exist today — a new data model / business decision) and scope each handler to it. |
| F5 | MEDIUM | **N+1 on kiosk-polled surfaces.** The kiosk (30 s auto-refresh) issues ~4 `search_count`/workcenter + ~3/family + a shop-wide late count = ~60+ counting queries per poll per tablet; the shop-daily rebuild loops days × 6 `_pull_*` searches with Python aggregation. | Collapse the per-WC/per-family counters into batched `read_group`; convert `_pull_*` to `read_group`. Self-contained but a non-trivial refactor. |
| F6 | LOW | `_check_production_approval_gate` (`sale_order.py`) is dead code (0 call sites) — a reader may think the SO-confirm gate is live. Harmless (the MO-create gate is the real one). | Optional: delete it, or restore intentionally. Left in place to minimise churn. |
| — | — | **Cross-module test artifacts** (dependency `southbrook_estimating_website`): `test_send_to_manufacturing.test_rejects_draft_order_with_wrong_state` returns `not_approved` instead of `wrong_state`, and `test_re_fire_reuses_existing_mo` — both surface only when mrp_pm's approval gate is installed (correct new precedence: approval checked before state). | Update those tests in a combined-stack pass; belongs to the dependency module, out of scope here. |

---

## Strong positives (verified)

- **Defense-in-depth at MO create** (`mrp_production.py`) with the correct
  procurement/stock-rule carve-out; cross-module fields consistently
  `getattr`/`in _fields`-guarded and excluded from `@api.depends`.
- **No SQL injection** (the one raw query is fully parameterized); **no unsafe
  render** (`t-esc` throughout; `Markup(_())%dict` auto-escapes chatter); routes
  `type="jsonrpc"`, `auth="user"` (no public kiosk data leak).
- **v19-clean**: no `<function obj()>` install trap, correct v19 `ir.cron` schema,
  `models.Constraint`, `group_ids`, `<list>`; all cross-module xmlids/fields
  resolve to source; `self.env` on the controller is valid in v19.

---

## Validation

- `-i southbrook_mrp_pm` (fresh DB, 118 modules) — **clean install**, registry 34 s.
- `-u southbrook_mrp_pm` — **clean upgrade**, idempotent.
- Tests `--test-tags=/southbrook_mrp_pm` — **32/32 pass, 0 failed, 0 errors**
  (1 skipped: MI-dependent), from a baseline of **7 failures**. See `TEST_RESULTS.md`.
