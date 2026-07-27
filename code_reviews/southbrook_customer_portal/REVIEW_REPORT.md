# Code Review — `southbrook_customer_portal`

**Module #33 of 46 · Odoo 19.0 CE**
**Version:** 19.0.0.7.0 → **19.0.0.8.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security; v19+correctness) → independent
source verification → HEAD baseline → minimal real fixes + regression test → live
`-i`+`-u`+tests on isolated DB (`ci_cportal`).

## What the module does
Customer-facing `/my/kitchen-projects` portal: review design concepts (A/B/C),
select one, and approve — plus a `/my/fabio` customer Q&A page. Small (905 LOC),
portal/website-facing.

## Verdict
**Well-built and v19-clean.** Both agents confirm: correct IDOR/ownership checks,
record-rule scoping, CSRF on every POST, no XSS (no `t-raw`), no mass-assignment,
approve flow state-gated, Fabio customer-scope isolated. Install/upgrade clean,
all cross-module refs resolve. Two real fixes (one integrity, one correctness);
everything else documented.

## Findings

### Fixed
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **F1** | MEDIUM | **`select_option` had no server-side state gate.** Ownership + option-belongs-to-project were checked, but not project state — only the template *hid* the button. A customer (holding a valid CSRF token from any of their own pages) could POST `/my/kitchen-project/<own>/select/<other_option>` **after approval**, silently re-pointing `selected_design_option_id` to a different concept than the one approved (desyncing an already-generated quote/MO/spec-sheet), with no re-approval or audit. | Added a `project.state in ("designing","awaiting_customer")` gate (mirrors the `approve` route). +1 regression test. |
| **F3** | LOW | `date_decided` on the portal-created approval was **always None** — `http.fields.Datetime.now() if hasattr(http, "fields")` (`odoo.http` has no `fields`), so the guard never fired. Approvals sorted with a NULL decision date. | `from odoo import fields`; `fields.Datetime.now()`. |

### Documented (not changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| F2 | LOW | The spec-sheet PDF link (`/report/pdf/.../<sale_order_id>`, stock `auth=user` report route) has no access token — IDOR protection relies **entirely** on the `sale.order` portal record rule in the estimating/sale layer. Not a confirmed leak (standard record rules block it). | Verify the `sale.order` portal rule is `partner_id`-scoped; consider an access token for defense-in-depth. |
| — | cosmetic | Sidebar passes `kitchen_project_count`/`fabio_question_count` placeholders never populated (module doesn't override `_prepare_home_portal_values`) — v19 renders the entry gracefully with no badge. | Override `_prepare_home_portal_values` to show counts. |
| — | design | The approve route `create({"state":"approved"})` bypasses `sb.kitchen.approval.write()`'s transition guard (create is the intended path; guard only inspects write vals). | Acceptable; route through `action_approve()` if portal approvals should share the guarded transition. |

## Strong positives (verified)
- **Ownership**: `_fetch_project_for_user` sudo-browses then compares `partner_id`,
  returning the same `MissingError` for not-found and not-owned (no existence leak);
  covered by `test_portal_acl` with a real second portal user.
- **Record rules + ACL** scope portal read to own `partner_id` with write/create/
  unlink=0; all writes go through gated `.sudo()` in the controller.
- Every mutating route is `auth="user"` + POST + `csrf=True`; no public route
  mutates. No mass-assignment, no client-supplied domain, no SQL/`eval`.
- **No XSS** (zero `t-raw`; `t-field`/`t-out` escape AI/customer text). Fabio
  customer scope isolated from the internal-users disclosure path.
- **v19-clean**: `type="http"`, no `type=json`, all portal `t-call`/inherit/xpath
  targets exist in v19 core, all cross-module fields traced to source.

## Validation
- `-i` (fresh DB) — clean install, registry ~42 s.
- `-u` — clean.
- Tests `--test-tags=/southbrook_customer_portal` — **10/10 pass** (9 baseline + 1
  new F1 regression test). See `TEST_RESULTS.md`.
