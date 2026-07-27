# CHANGELOG — `southbrook_kitchen_mrp`

## 19.0.1.6.0 — 2026-07-11 — Code-review pass (Module #22)

### Fixed
- **[HIGH] Cabinet Label PDF no longer crashes on print.** The report used
  `hasattr(o, 'pg_revision_code')`, which is unavailable in the `ir.qweb` report
  eval context (only mail templates inject it) — so every label render raised
  `TypeError: 'NoneType' object is not callable`. Replaced with
  `'pg_revision_code' in o._fields and o.pg_revision_code` (QWeb-legal). Also
  fixed the label test's naive `assertNotIn('sbk-rev-row')` (which matched the
  CSS class, not the row element). `reports/cabinet_label_report.xml`,
  `tests/test_cabinet_label_w007.py`.
- **[MEDIUM] Records are named properly, not "New".** Added the missing
  `ir.sequence` records for `sb.cutlist` / `sb.hardware.package` /
  `sb.production.package` (the create()s called `next_by_code` with no seed data
  → all records fell back to "New"). `data/ir_sequence.xml`, `__manifest__.py`.
- **[MEDIUM] `pkg` QR scan degrades gracefully** when `southbrook_floor_traveler`
  isn't installed (the `record_scan` method lives there and can't be a dep — it
  would loop) — `hasattr` guard → clean `UserError` instead of `AttributeError`.
  `models/qr_kind_handlers.py`.
- **[LOW] Nesting scrap-create failures are now logged** (was a silent
  `except: pass` that flipped the cutlist to `nested` with no scrap, no trace).
  `models/sb_cutlist.py`.

### Notes (documented, not changed)
- Cross-module: a signed `pkg` QR + read-only mrp_user reaches
  `wo.sudo().button_finish()` in southbrook_floor_traveler (address there).
- No multi-company scoping on the package models; RPC orchestration methods are
  mrp_user-callable (ACL-bounded); undeclared `southbrook_dims` top-level import;
  `tracking=True` without mail.thread is a no-op.
- Security audit confirmed: no SSRF/eval/SQL/XSS; BoM cron is private/idempotent/
  non-destructive; QR dispatch HMAC-signed + ACL-gated; hardware resolve()
  already batched; FK indexing complete.
