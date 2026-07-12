# Code Review — `southbrook_kitchen_workspace` (Module #13, Tier 3)

**Version:** 19.0.0.5.0 → **19.0.0.6.0**
**Reviewed:** 2026-07-11
**Scope:** ~1280 LOC — 7 models, 7 views, 3 data XML (incl. mail templates + appliance catalog), ACL, tests. No controllers.
**Method:** Two independent parallel audits (v19-compat + code; security + performance); every HIGH/MEDIUM claim re-verified against source before editing.

---

## Executive Summary

The designer-facing kitchen-project workspace is a **small, clean, low-defect module**. The v19-compat audit found it **v19-clean** (correct `@api.model_create_multi`, `<list>` views, attribute-domains, `<chatter/>`, no `_sql_constraints`/`name_get`/removed-APIs, both `@api.depends` resolve against real fields incl. cross-module `sale_order_id.room_ids`). The security audit confirmed **no CRITICAL** exposure: **no controllers, no external LLM call, no API key, no `eval`/SQL, no `sanitize=False`, injection-safe mail templates** — several worst-case concerns simply don't exist here. Every finding is an **internal-user-gated integrity/SoD/audit** issue, not a remote exploit.

Fixed: **1 HIGH integrity, 2 MEDIUM audit-bypass, 1 MEDIUM broken-CTA, plus 4 LOW** (perf/indexes/mail-context/dead-code). Install + upgrade clean; **23/23 tests green** including a new approval-state-write-guard regression test. The one policy-dependent finding (who may approve) is documented, not forced.

---

## Original Issues Found

### Fixed

| # | Sev | Title | Root cause |
|---|-----|-------|-----------|
| H1b | HIGH (integrity) | Approval `state` was directly writable, bypassing the state guard | `action_approve/reject` guard on `state=='pending'`, but the ACL grants `write` and `state` had no readonly/write-guard → a **rejected** approval could be flipped to **approved** via direct ORM/UI write, skipping the guard entirely. |
| M2 | MEDIUM (audit bypass) | `confirmed_by_human` safety gate bypassable, dropping the audit stamp | The GAP-02 human-confirmation gate was an editable `boolean_toggle`. `action_confirm` stamps `confirmed_by_user_id`/`confirmed_at`, but a direct toggle set `confirmed_by_human=True` **without** those stamps — no record of who confirmed AI dimensions the config/cutlist engine then trusts. Same on `sb.kitchen.appliance`. |
| M1 | MEDIUM (audit deletion) | Any employee could delete approval + AI-analysis audit records | ACL granted `perm_unlink=1` to `base.group_user` on `sb.kitchen.approval` and `sb.kitchen.ai.analysis` — both `mail.thread` audit-bearing — so anyone could destroy another designer's approval/chatter history. |
| V-MED | MEDIUM (correctness) | Broken "Open project" CTA in two operator emails | `data/mail_templates.xml:74,109` linked `/odoo/action-base.action_open_view_form_view/…` — **not a real action xmlid** → dead button in the released-to-production and design-approved emails. |
| L1 | LOW (perf) | N+1 `search()` in `design.option.write` | One-of-N enforcement issued a `search()` per selected record; batched into one. |
| L3 | LOW (perf) | Missing indexes on filter fields | `project.state`, `project.salesperson_id`, `approval.state` (the obvious kanban/"my projects" axes) were unindexed. |
| V-L1 | LOW (correctness) | `fields.Date.today()` in a mail body | `mail_templates.xml:149` — `fields` isn't in the mail render context (latent; short-circuited today). Now `format_date(object.date_completed)`. |
| V-L2 | LOW (code) | Dead `Template = …sudo()` dropped the sudo intent; inline logger | `_send_lifecycle_email` built a sudo'd template then sent via the non-sudo `env.ref` result. |

### Documented for owner decision (NOT auto-applied)

| # | Sev | Title | Why not auto-fixed |
|---|-----|-------|--------------------|
| D1 | HIGH (policy) | Approval actions have no group gating; `approver_type` is decorative | Whether an `Estimator` may fire `production_release`, or an approver must match `approver_type`, or approver ≠ requester — is a **business-policy** call. Hard-gating to a manager group could break a small/solo shop. The H1b fix already closes the *integrity* hole (state can't be laundered); *who* may approve is the owner's decision. Recommendation + ready pattern provided. |
| D2 | (policy) | No `ir.rule` per-designer isolation (shared read/write across designers) | Consistent with the internal-staff-shared-visibility model used elsewhere in the stack; flag only, not a change. |

---

## Repairs Completed
- **H1b** — added a `write()` override on `sb.kitchen.approval` refusing `state` changes unless the `sb_approval_transition` context flag is set (only `action_approve`/`action_reject` set it); made `state` readonly in the view. New regression test `test_approval_state_not_writable_directly`.
- **M2** — `confirmed_by_human` set `readonly="1"` in the ai-analysis, appliance, and project-embed views (driven only via `action_confirm`/`action_unconfirm`, preserving the audit stamp).
- **M1** — ACL: `perm_unlink=0` for `base.group_user` on approval + ai-analysis; added `sales_team.group_sale_manager` rows with full CRUD.
- **V-MED** — repointed both broken CTAs to `southbrook_kitchen_workspace.action_sb_kitchen_project` (a real action; both emails go to internal salespeople, so a backend deep-link is correct).
- **L1** — `design.option.write` now does one batched `search([('project_id','in',…)])`.
- **L3** — `index=True` on `project.state`, `project.salesperson_id`, `approval.state`.
- **V-L1** — `format_date(object.date_completed)` in the project-done mail.
- **V-L2** — send via `template.sudo()`; hoisted `_logger` to module scope.

## Files Changed
`models/sb_kitchen_approval.py`, `models/sb_kitchen_project.py`, `models/sb_kitchen_design_option.py`, `security/ir.model.access.csv`, `data/mail_templates.xml`, `views/sb_kitchen_approval_views.xml`, `views/sb_kitchen_ai_analysis_views.xml`, `views/sb_kitchen_appliance_views.xml`, `views/sb_kitchen_project_views.xml`, `tests/test_kitchen_project.py`, `__manifest__.py`.

## Database Impact
- ACL: audit-record `unlink` moved from every employee to managers (grant tightening).
- New indexes on `state`/`salesperson_id` (additive). No schema/migration; no field type changes.

## Security Improvements
- Approval state can no longer be laundered via direct write (H1b).
- AI/appliance confirmation audit stamp can no longer be bypassed (M2).
- Audit records no longer deletable by arbitrary employees (M1).
- Residual (documented): D1 (who-may-approve policy), D2 (per-designer isolation).

## Performance Improvements
- One-of-N selection de-looped (L1); filter-field indexes added (L3).

## Remaining Risks
- **D1**: until the owner decides approval group-gating, any internal user can still *approve* (they just can't forge the state outside the action). For a multi-designer shop, gate `eng_review`/`production_release` to managers.

## Recommendations (priority)
1. **D1** — decide approval group-gating + `approver_type`↔user-group enforcement.
2. Consider a reviewer group for `confirmed_by_human` if AI-dimension sign-off should be restricted beyond "any internal user".
3. **D2** — decide per-designer record-rule scoping vs. intended shared visibility.
