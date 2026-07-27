# Changelog — `southbrook_mrp_kitchen_workcenters`

## 19.0.5.0.0 — 2026-07-11 (code-review pass, module #31)

### v19 core drift — Fixed
- **D1** — added `mail.thread` to `mrp.workorder` `_inherit` (v19 dropped it from
  core; the module posts WO chatter in downtime/raise-ECO/subcontract/report-
  problem, which was crashing with `AttributeError` on `message_post`/`message_ids`).
- **D2** — `test_w042` uses `mrp.production.lot_producing_ids` (v19 plural M2M; the
  module code was already correct, the test lagged).
- **D3** — removed the removed-in-v19 `mo._onchange_move_raw()` call from `test_w026`.
- **D4** — `test_asbuilt_pg_backrefs` asserts `field.related` as the dotted string
  (v19 format), not a tuple.
- **D5** — `test_w011` sets `test_enable` in context explicitly (v19 doesn't inject
  it); `test_w054` gives its test users `mrp.group_mrp_user` (needed to read the WO).

### Correctness / robustness — Fixed
- **C1** — subcontract-decision wizard: removed `required=True` from
  `selected_vendor_id` (a NOT NULL column made the open-empty wizard's `create()`
  always fail; `action_confirm` already validates the vendor).
- **C2** — `mrp_workorder._sbk_maybe_log_form_open` guards the unbound-request
  access (`getattr(request, "httprequest", ...)` raised `RuntimeError` when
  `web_read` runs outside HTTP).

### Security — Fixed
- **M2 (HIGH)** — `DefectQrKind.handle_action`: reject `share` (portal) users
  (defect scanning is a staff action — the stateless `defect` kind ran no
  `check_access` and created NCRs under `sudo`), and validate the supplied
  `workorder_id` via `check_access("read")` before linking (was trusted as-is → an
  IDOR pinning fabricated NCRs onto any WO).
- **M3 (MEDIUM)** — report-problem wizard maps its downtime-reason keys to the
  downtime model's Selection keys (4 of 6 were invalid → `ValueError` aborted the
  atomic submit).

### Not changed (documented in REVIEW_REPORT.md)
- H1 CSRF-able mutating-GET + no-TTL QR (root fix in `southbrook_qr_kit`'s
  `scan_get`; TTL on this module's handlers), M4 per-transition authz, M5 OPC-UA
  state-write (stub-only), LOWs (bare-except quarantine, `check_access_rights`
  deprecation, MO-name prefix fan-out, N+1 computes, OPC-UA plaintext password),
  and the 4 remaining pre-existing test-harness failures (w018 HTTP-context, w026
  malformed-PNG).
