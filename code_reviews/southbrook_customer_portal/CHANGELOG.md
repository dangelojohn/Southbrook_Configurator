# Changelog — `southbrook_customer_portal`

## 19.0.0.8.0 — 2026-07-11 (code-review pass, module #33)

### Fixed
- **F1 (MEDIUM) — post-approval design tampering.** `kitchen_project_select_option`
  now gates on `project.state in ("designing","awaiting_customer")` before writing
  `is_selected` (the template only hid the button; a customer could POST directly
  with a valid CSRF token to re-point the selected concept after approval). +1
  regression test (`test_select_option_blocked_after_approval`).
- **F3 (LOW) — `date_decided` never recorded.** `from odoo import fields` and
  `fields.Datetime.now()` (was `http.fields.Datetime.now()` — `odoo.http` has no
  `fields`, so the value was always None).

### Not changed (documented in REVIEW_REPORT.md)
- F2 spec-sheet PDF report-route relies on the sale.order portal record rule
  (verify/consider access token), sidebar count placeholders (cosmetic), approve
  route create bypasses the write-transition guard (design note).
