# Changelog — `southbrook_hermes` ("Fabio")

## 19.0.5.0.0 — 2026-07-11 (code-review pass, module #32)

### Security — Fixed
- **S1 (HIGH)** — `tools/write_tools.py draft_customer_email` no longer `sudo()`s;
  it browses as the acting user and enforces `check_access_rights/rule("write")` on
  the order (was a sudo-write IDOR — an LLM could post a note onto any order id).
- **S7 (LOW)** — `utils/jwt_helper.py verify_jwt` now passes
  `options={"require": ["exp"]}` (reject a forged token that omits expiry).

### v19 correctness — Fixed (were 500'ing the tool surface)
- **V2 (HIGH)** — `read_tools.get_order_status` uses the real `project.task`
  readiness field names (`top_blocker`/`next_best_action`/`readiness_score`/
  `current_bottleneck_workcenter_id`, not the nonexistent `southbrook_`-prefixed
  ones) and `getattr`-guards them (the fields come from `southbrook_project_mrp`,
  not a hermes dependency).
- **V3 (HIGH)** — `_count_mos_for_order` searches `mrp.production.sale_line_id`
  (sale_mrp) instead of the nonexistent `sale_order_line_id` (was `ValueError`/500).
- **V5 (MED)** — kitchen-project tools use `design_option_ids` (real field) instead
  of `option_ids` (which never resolved → 0 options).

### Tests
- `test_fabio_ask.test_internal_answer_describes_base_production_users` creates the
  "base production" users the answer describes (demo-seeded in the full stack;
  absent in the no-demo test DB).
- `test_fabio_ask.test_customer_pricing_without_projects_is_graceful` asserts the
  actual graceful wording ("no projects").
- (Env) PyJWT installed in the test container so the 3 JWT-helper tests run.

### Not changed (documented in REVIEW_REPORT.md)
- S2 per-user cost cap, S3 auto_apply gate, S4 SoD, S5 os_section slug allowlist,
  S6 conversation-log ownership, V1 `check_access_rights` deprecation (shims work in
  this build), V6/misc (`read_group`, `utcnow`, JSON-schema, `implied_ids`,
  manifest `external_dependencies`).
