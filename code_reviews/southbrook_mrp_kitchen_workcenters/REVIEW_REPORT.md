# Code Review — `southbrook_mrp_kitchen_workcenters`

**Module #31 of 46 · Odoo 19.0 CE**
**Version:** 19.0.4.48.7 → **19.0.5.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+perf; v19+data) → independent source
verification → HEAD baseline → minimal real fixes + test repairs → live `-i` + `-u`
+ tests on isolated DB (`ci_kwc`, full southbrook dep stack staged).

The largest module in the campaign (**13.3 kLOC**: routing, quality/NCR, downtime,
as-built, capacity, OPC-UA machine integration, shift handover, QR shop-floor
actions, a defect-sheet controller, 3 wizards, a WO-traveler report).

---

## Verdict

Install/data/views/report/demo are **v19-clean** (both agents confirm). But the
module was heavily **v19-core-drifted** on the current build (**35 of its 140 own
tests failed at baseline**) and carried two real security defects and a wizard-
crashing bug. All real defects fixed; **35 → 4 failures, zero regressions**. The 4
remaining are pre-existing test-harness artifacts (documented).

---

## Findings

### Fixed — v19 core drift (were breaking the module)

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| D1 | **HIGH** | **`mrp.workorder` lost `mail.thread` in v19** (prod's older build had it). The module posts shop-floor chatter to the WO in 4 places (downtime W069, raise-ECO W034, subcontract W066, report-problem W040) → `AttributeError: 'mrp.workorder' object has no attribute 'message_post'/'message_ids'` (~12 test errors). | Added `mail.thread` to the module's `mrp.workorder` `_inherit` (both agents confirm this is the right fix). |
| D2 | MEDIUM | **`mrp.production.lot_producing_id` → `lot_producing_ids`** (Many2many) in v19. The module code was already correct (plural); the **test** still used the removed singular (search domain + write). | Updated `test_w042` to the plural field. |
| D3 | MEDIUM | Test called the removed v19 onchange `mo._onchange_move_raw()` (`action_confirm` builds the moves now). | Removed the call (`test_w026`). |
| D4 | LOW | `test_asbuilt_pg_backrefs` asserted `field.related == ("production_id","pg_ebom_id")` (a tuple); v19 exposes `field.related` as the dotted **string**. | Updated 4 assertions to the string form. |
| D5 | LOW | W011 form-open-log guard relied on the framework injecting `test_enable` into the env **context**; v19 only sets the config flag. | `test_w011` sets the context key explicitly; `test_w054` gives its bare test users `mrp.group_mrp_user` (they couldn't read the WO). |

### Fixed — correctness / robustness

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| C1 | **HIGH** | **Subcontract-decision wizard couldn't be opened.** `selected_vendor_id` was `required=True` (NOT NULL) on a wizard that's opened empty then filled → `create()` always failed (8 test errors). `action_confirm` already validates the vendor. | Removed field-level `required=` (the confirm action is the real gate). |
| C2 | MEDIUM | **`_sbk_maybe_log_form_open` crashed on an unbound request.** `getattr(request, "httprequest", None)` raises `RuntimeError` (LocalProxy) when `web_read` is called outside HTTP (cron/internal/test). | Guarded the request access with `try/except RuntimeError`. |

### Fixed — security

| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **M2** | **HIGH (privesc/IDOR)** | **`DefectQrKind` created NCRs with `sudo()` and an attacker-chosen WO id.** The `defect` kind is stateless (`get_record` returns empty → **no `check_access`**), so any `auth="user"` (incl. **portal**) user holding a signed, never-expiring `sb://defect/…` payload (embedded on the `auth=user` defect-sheet) could mint superuser NCRs and pin a fabricated `fail` NCR onto **any** work-order id. | Reject `share` (portal) users (a defect scan is a staff action); validate `workorder_id` via `check_access("read")` before linking. |
| **M3** | **MEDIUM** | **Report-Problem wizard wrote invalid downtime-reason keys.** 4 of the 6 `WIZARD_DOWNTIME_REASONS` (`material_shortage`, `changeover`, `quality_hold`, `operator_break`) aren't valid `southbrook.kitchen.workcenter.downtime` Selection keys → `ValueError` inside the atomic savepoint aborted the **whole** scrap+defect+downtime submit for those reasons. | Added a wizard-key → model-key mapping. |

### Documented (business-policy / infra / cross-module — not unilaterally changed)

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| H1 | HIGH | **Mutating QR actions are triggerable via CSRF-able GET, permanently.** This module mints `…/sb/qr/scan?p=<signed>&action=finish` QR URLs on the WO traveler; the qr-kit dep's `scan_get` forwards any `action` to the handler, and `type=http` GET has no CSRF — an `<img src=…&action=finish>` finishes/seals/quarantines a record as a logged-in manager. `wo/mo/asbuilt` payloads have **no TTL** (permanent capability). | **Root fix belongs in `southbrook_qr_kit`**: `scan_get` must accept only read/open actions via GET and require POST for mutations. This module should give `wo/mo/asbuilt` handlers a short `_expires_in_seconds`. Cross-module architecture change. |
| M4 | MEDIUM | Handler-layer authorization is "read-gated" for privileged transitions (relies solely on ORM write-ACL running as the actor; any future handler adding an internal `sudo` — as `DefectQrKind` did — silently escalates). | Add explicit per-transition capability checks in the handlers. |
| M5 | MEDIUM | OPC-UA `action_simulate_poll` can write `mrp.workorder.state` directly (state laundering) via QR `poll` gated on read. **Stub-only** — `_poll_endpoint_real` raises `NotImplementedError`; no network call → **no SSRF**; value comes from admin-configured `stub_value`, not scan input. | Guard the state write behind the WO state machine when the real poll lands. |
| LOW | LOW | `mi_check.write` swallows quarantine failures (bare `except`); `check_access_rights/_rule` used (v19 shims, deprecated); MO-name `=ilike` prefix fan-out can hit a wrong record; N+1 non-stored computes (`_compute_x_sbk_rework_metrics`/`_downtime`); OPC-UA plaintext password (self-acknowledged TODO). | Migrate to `check_access`; store the N+1 flags; encrypt the OPC-UA password when the real integration lands. |

### Remaining pre-existing test failures (documented, not caused by this pass)

4 errors survive (all in the first baseline; zero regressions):
- `test_w018` (×2) — the QR defect handler is designed for HTTP dispatch; called
  directly in a `TransactionCase` it hits request-bound accesses (v19 lazy-gettext
  `_get_lang(frame)` / `message_post`). Works via the real `/sb/qr/scan` route;
  the tests should be `HttpCase`.
- `test_w026` (×2) — the WO-traveler report fails PIL rendering on the test's
  **malformed PNG** data (`chunk_IE` truncated PNG). Report/image-data robustness.

---

## Strong positives (verified)

- **No RCE/SSRF** — OPC-UA is genuinely stub-only (no network call anywhere).
- HMAC signature verified **before** record resolution; base `get_record` enforces
  `check_access("read")`; W040 wizard uses a real savepoint (atomic); subcontract
  wizard validates `vendor ∈ candidates` and never mutates canonical BOM routing.
- Capacity cron bounded + idempotent + field-guarded; downtime model has
  date/duration constraints; XSS escaped in the sibling controller.
- **v19-clean install**: no `<function obj()>` trap, correct `ir.cron`/`ir.sequence`
  schema, `models.Constraint`, all `@api.depends` resolve, all view xpaths + the
  report render, all cross-module fields traced to source.

---

## Validation

- `-i` (fresh DB, 164 modules, incl. the `mail.thread` column on `mrp.workorder`
  + all 8 data seeds) — **clean install**, registry ~47 s.
- `-u` — clean.
- Tests `--test-tags=/southbrook_mrp_kitchen_workcenters` — **136 pass, 0 failed, 4
  errors** (all pre-existing, documented), from a baseline of **35 failures**. See
  `TEST_RESULTS.md`.
