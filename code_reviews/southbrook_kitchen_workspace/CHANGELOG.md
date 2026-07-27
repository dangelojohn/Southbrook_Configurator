# CHANGELOG — `southbrook_kitchen_workspace`

## 19.0.0.6.0 — 2026-07-11 — Code-review pass (Module #13)

### Security / integrity
- **[HIGH] Approval state is now transition-only.** Added a `write()` guard on
  `sb.kitchen.approval` refusing direct `state` writes unless made through the
  Approve/Reject actions; `state` is readonly in the view. Previously a rejected
  approval could be flipped to approved by a direct ORM/UI write, bypassing the
  pending-guard. `models/sb_kitchen_approval.py`, `views/sb_kitchen_approval_views.xml`.
- **[MEDIUM] AI/appliance confirmation gate can't bypass its audit stamp.**
  `confirmed_by_human` is readonly in all views (ai-analysis, appliance, project
  embed) and driven only via `action_confirm`/`action_unconfirm`, which stamp
  `confirmed_by_user_id`/`confirmed_at`. `views/*`.
- **[MEDIUM] Audit records no longer deletable by every employee.** Dropped
  `perm_unlink` for `base.group_user` on `sb.kitchen.approval` and
  `sb.kitchen.ai.analysis`; added manager rows with full CRUD.
  `security/ir.model.access.csv`.

### Fixed
- **[MEDIUM] Broken "Open project" CTA** in the released-to-production and
  design-approved emails — `base.action_open_view_form_view` isn't a real xmlid;
  repointed to `southbrook_kitchen_workspace.action_sb_kitchen_project`.
  `data/mail_templates.xml`.
- **[LOW] `fields.Date.today()` in a mail body** (`fields` not in the render
  context) → `format_date(object.date_completed)`. `data/mail_templates.xml`.
- **[LOW] Lifecycle email send** now runs on the sudo'd template (the sudo intent
  was silently dropped); hoisted the logger to module scope.
  `models/sb_kitchen_project.py`.
- **[LOW] N+1 in `design.option.write`** one-of-N enforcement → single batched
  `search`. `models/sb_kitchen_design_option.py`.
- **[LOW] Added indexes** on `project.state`, `project.salesperson_id`,
  `approval.state`.

### Tests
- Added `test_approval_state_not_writable_directly`. Result: **23/23 green**
  (install + upgrade); all existing lifecycle/email/selection tests still pass.

### Notes (unchanged by design — owner decisions)
- Approval actions are not group-gated and `approver_type` is not enforced (who
  may approve is a business-policy call; hard-gating could block a small shop) — D1.
- No per-designer record-rule isolation (intended internal-shared visibility) — D2.
