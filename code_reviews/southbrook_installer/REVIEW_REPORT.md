# Code Review & Repair Report — `southbrook_installer`

**Module:** Southbrook Cabinet Installer · **Version:** 19.0.3.0.0 → **19.0.4.0.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 Community Edition
**Queue position:** #4 of 46 (Tier 0 — leaf; deps all standard Odoo)
**Review method:** 3 parallel read-only audit agents + independent source verification + **baseline & post-fix test runs** on Odoo 19 CE.

---

## Executive Summary

A substantial, well-engineered module (~7,860 LOC, 14 models): installer job lifecycle (8-stage state machine, 11-phase photo-gated log, GPS, builder sign-off, damage flags, delivery manifest, tool loans, closeout, punchlist), an OWL dispatch board, 2 QWeb reports, and role-based security.

**Hygiene is excellent** — no `_sql_constraints` (uses `models.Constraint`), no `sudo()`, no `cr.execute`, no controllers, correct `@api.model_create_multi`, valid v19 dashboard services, `t-out` reports, comprehensive ACLs. The **baseline test suite was green** (25 tests). But the deep audit found two serious latent issues plus perf gaps:

- **A CRITICAL v19 regression:** `bus.bus._sendmany()` was **removed in v19** — every damage-flag create/resolve called it → `AttributeError`, swallowed by a broad `except`, so the **entire live-dispatcher-bus feature was silently dead** (the board degraded to 30s polling with a false "🟢 live" indicator).
- **A CRITICAL security gap:** the module ships **zero `ir.rule`** despite group docs stating crew "view **assigned** jobs" — so every role (even the lowest helper) saw *all* jobs company-wide: customer addresses, GPS, photos, builder signatures.

Both fixed and proven by new tests; the suite is now **28/28 green**.

---

## Original Issues Found

| # | Sev | Axis | Finding |
|---|-----|------|---------|
| V1 | **CRITICAL** | v19 | `bus.bus._sendmany([...])` (`southbrook_damage_flag.py:377`) — method removed in v19. Raised `AttributeError` on every flag create/resolve (swallowed) → live dispatcher bus dead, silent poll fallback. |
| S1 | **CRITICAL** | Security | No `ir.rule` anywhere → every SAMI role sees every job's PII (address/GPS/photos/signatures), contradicting the documented "helper views assigned jobs" model. |
| P1 | **HIGH** | Perf | `stage_is_terminal` — the default filter on every Jobs list/kanban + the dashboard default — was **unindexed** (every sibling boolean is indexed). |
| P2 | MED | Perf | 4 dashboard counters (`tool_loan_count`, `tool_loan_open_count`, `stage_log_count`, `stage_log_done_count`) were `store=False` but fetched for ≤200 jobs on every dashboard load + 30s poll → recurring recompute. |
| P3 | MED | Perf | `_spawn_phase_logs` re-queried phases + dispatched `Log.create` once **per job** (N searches/creates on bulk create). |
| C1 | LOW | Code | Dead `stage_id.sequence` dependency in `_compute_color`. |
| D1 | MED | Docs/logic | "2-hour deadline" claim on the dispatcher activity is unachievable (`mail.activity.date_deadline` is a `Date`). |
| S2 | MED | Security | Dispatch-board client action gated only by menu (not the action). |

### Reviewed and found clean
All 13 v19-breakage axes (constraints, groups/`group_ids`, cron, AbstractModel, `@api.depends` on ~28 computes, view validation, dashboard services, decorators, `env.company`, ACL completeness across all 14 models, load order, QWeb `t-out`), the state-machine gate collection (all-failures-in-one-`UserError`), no SQL/sudo/eval, indexes otherwise consistently correct, bounded searches, the barcode-scan hot path. The module shows clear evidence of having learned the codebase's recurring traps (inline comments cite them).

---

## Repairs Completed

1. **V1 (CRITICAL):** `_sendmany([...])` → `_sendone("sami_installer", "installer_update", payload)` — restores the live dispatcher bus. Regression test added asserting `_notify_dispatcher_bus` no longer raises.
2. **S1 (CRITICAL):** new `security/southbrook_installer_record_rules.xml` — 14 rules across job + 6 PII-bearing child models (stage_log, damage_flag, delivery_manifest, tool_loan, closeout, punchlist). Crew (helper/lead) see only jobs they lead or are crewed on; dispatcher/warehouse/finance/ops keep company-wide visibility (via the `implied_ids` chain + Odoo's OR-of-group-rules semantics). **Two tests prove both directions.**
3. **P1 (HIGH):** `index=True` on `stage_is_terminal`.
4. **P2 (MED):** `store=True` on the 4 dashboard counters (deps already correct).
5. **P3 (MED):** `_spawn_phase_logs` batched — phases queried once, one `Log.create` across the whole job batch.
6. **C1 (LOW):** trimmed the dead `stage_id.sequence` dependency.
7. **D1:** corrected the misleading "2-hour deadline" docstring (documents the `Date`-field limitation; behavior unchanged: same-day-urgent + ⚠ summary).
8. **S2:** attempted a `groups_id` on the client action — **reverted** because `ir.actions.client` has no `groups_id` in v19 (would break install). Instead documented: the menu `groups=` plus the new record rules cover it (a non-dispatcher who force-invokes the board sees only their own scoped jobs, since the OWL `searchRead` respects record rules).

### Deliberately NOT changed (documented as recommendations)
- **`action_confirm_all_ok` per-line writes** (MED perf, bounded at 250 lines): deferred — `qty_received_ok` differs per line, so batching needs a careful refactor of `action_set_ok`; not worth the regression risk now.
- **Missing app icon** (`web_icon` → nonexistent `static/description/icon.png`, LOW): packaging cosmetic; needs a design asset.
- **`closeout.tool.line`/`material.line` missing warehouse ACL rows** (LOW): fail-safe (warehouse can't *see* the lines, no leak) — I'm conservative about *adding* access grants without confirmed intent.
- **Multi-company `company_id`** (LOW): deferred — single-company deployment.

---

## Files Changed
5 modified, 2 new (`security/southbrook_installer_record_rules.xml`, `tests/test_southbrook_installer_security.py`).

## Database Impact
- 1 new index (`stage_is_terminal`), 4 columns now materialized (the stored counters — recomputed on upgrade), **14 new `ir.rule`** records.
- No column drops / type changes. Forward-compatible.
- **The record rules are a live-behavior change** — see Remaining Risks.

## Security Improvements
Closed the cross-crew PII exposure (addresses/GPS/photos/signatures) via 14 record rules enforcing the documented per-installer model; verified by tests that crew are scoped and broad roles retain full visibility.

## Performance Improvements
Indexed the universal default filter; stored the dashboard-polled counters; batched phase-log spawning on bulk create.

## Testing Results
_See `TEST_RESULTS.md`._ Baseline **25/25 green**; after repairs **28/28 green** (+3: bus regression, crew-scoping, dispatcher-full-visibility). Install validated clean; index + stored columns + 14 rules confirmed in the DB.

## Remaining Risks
1. **Record rules are a visibility behavior change (owner confirmation recommended before deploy).** After this loads, crew see only jobs where they're `lead_installer_id` (already required) or in `assigned_crew_ids`. If prod jobs lack crew assignments, those crew won't see them — populate `assigned_crew_ids`, or confirm the shop actually wants all-crew visibility (in which case drop the restrictive rules). Broad roles are unaffected.
2. Deferred MEDIUM/LOW items above (confirm-all batching, app icon, warehouse closeout-line ACL, multi-company).

## Recommendations
- **Deploy V1 (bus fix) promptly** — the dispatcher live feature is currently dead in prod.
- **Confirm the record-rule visibility model** before deploying S1, and ensure crew assignments are populated.
